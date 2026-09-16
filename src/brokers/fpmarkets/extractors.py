import calendar
import json
import re
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from src.common.config import DEBUG_SNAPSHOTS, random_sleep
from src.common.logger import log
from src.common.playwright_utils import evaluate_with_frame_fallback, wait_for_evaluate
from src.brokers.fpmarkets.config import DEBUG_DIR
from src.brokers.fpmarkets.navigation import click_instruments_tab, click_trading_tab

_MONTH_ABBR_TO_NUM = {abbr.lower(): idx for idx, abbr in enumerate(calendar.month_abbr) if abbr}

_JS_INDICATORS_EXTRACTOR = """
    () => {
        const data = {};

        // Top Header Summary (Return (total), Return (1D), Age (Days))
        const overviewBlocks = document.querySelectorAll("[class*='overview'][class*='item']");
        overviewBlocks.forEach(block => {
            const valElem = block.querySelector("[class*='overview'][class*='value']");
            const lblElem = block.querySelector("[class*='overview'][class*='label']");
            if (valElem && lblElem) {
                const val = valElem.textContent.trim();
                const lbl = lblElem.textContent.trim().toLowerCase();

                if (lbl.includes("return (total)")) data["return_total"] = val;
                else if (lbl.includes("return (1d)")) data["return_1d"] = val;
                else if (lbl.includes("age (days)") || lbl === "age") data["age_days"] = val;
            }
        });

        // Matched by substring rather than a fixed "_block"/"__block" class name: the
        // site has been observed serving both single- and double-underscore BEM class
        // variants (ta-indicators_block vs ta-indicators__block) for this same
        // component, so pin on "indicators" + "block" both being present instead of
        // the exact separator.
        const blocks = document.querySelectorAll("[class*='indicators'][class*='block']");
        blocks.forEach(block => {
            const valElem = block.querySelector("[class*='indicators'][class*='value']");
            const lblElem = block.querySelector("[class*='indicators'][class*='label']");
            if (valElem && lblElem) {
                const val = valElem.textContent.trim();
                const lbl = lblElem.textContent.trim().toLowerCase();

                // Return/period
                if (lbl === "all time") data["return_all_time"] = val;
                else if (lbl === "year") data["return_year"] = val;
                else if (lbl === "half year") data["return_half_year"] = val;
                else if (lbl === "quarter") data["return_quarter"] = val;
                else if (lbl === "month") data["return_month"] = val;
                else if (lbl === "week") data["return_week"] = val;
                else if (lbl === "day") data["return_day"] = val;

                // Monthly Section
                else if (lbl.includes("average return (weekly)") || lbl.includes("average return weekly")) data["avg_return_weekly"] = val;
                else if (lbl.includes("average return (monthly)") || lbl.includes("average return monthly")) data["avg_return_monthly"] = val;
                else if (lbl === "return deviation") data["return_deviation"] = val;
                else if (lbl.includes("return deviation (monthly)")) data["return_deviation_monthly"] = val;
                else if (lbl.includes("return deviation (yearly)")) data["return_deviation_yearly"] = val;

                // Trading tab
                else if (lbl.includes("return volatility (d)")) data["trading_return_volatility_d"] = val;
                else if (lbl.includes("recovery factor")) data["trading_recovery_factor"] = val;
                else if (lbl.includes("absolute gain")) data["trading_absolute_gain"] = val;
                else if (lbl.includes("downside deviation")) data["trading_downside_deviation"] = val;
                else if (lbl.includes("sharpe ratio")) data["trading_sharpe_ratio"] = val;
                else if (lbl.includes("volatility ratio")) data["trading_volatility_ratio"] = val;
            }
        });
        return data;
    }
"""

# Monthly bar chart (ApexCharts): each bar <path> carries the real data value in
# a "val" attribute and its category index in "j"; pair those with the x-axis
# month labels (in DOM order) rather than reading rendered bar heights.
_JS_MONTHLY_CHART_EXTRACTOR = """
    () => {
        // The Return tab renders multiple ApexCharts instances at once (the main
        // area chart "apexchartsincomeChartId", its range-selector mini chart
        // "apexchartsscrollBarChartId", and the bar chart we actually want,
        // "apexchartsmonthlyChartId"), all present in the DOM simultaneously. A
        // combined selector like "#apexchartsmonthlyChartId, .ta-chart svg" would
        // return whichever of those matches first in DOM order -- not necessarily
        // the monthly one -- so this must resolve the monthly chart's container by
        // ID alone, with no generic fallback that could grab a different chart.
        const chartRoot = document.querySelector("#apexchartsmonthlyChartId");
        if (!chartRoot) return {};

        const labels = Array.from(chartRoot.querySelectorAll(".apexcharts-xaxis-label tspan"))
            .map(el => el.textContent.trim())
            .filter(Boolean);

        const bars = Array.from(chartRoot.querySelectorAll("path.apexcharts-bar-area[val]"))
            .map(el => ({ j: parseInt(el.getAttribute("j"), 10), val: el.getAttribute("val") }))
            .filter(b => !Number.isNaN(b.j));

        const result = {};
        bars.forEach(b => {
            const label = labels[b.j];
            if (label !== undefined) result[label] = b.val;
        });
        return result;
    }
"""

# Max profit / Max drawdown: these two only live in the "Info" sidebar list (not
# the ta-indicators_block section above), scoped by its headline text so it
# can't merge with other .brs-list__entry sections elsewhere on the page (e.g.
# Trade Statistics on the Instruments tab). The other three entries in that
# same list (Sharpe ratio, Recovery factor, Volatility ratio) are duplicates
# of the trading_* fields above and are skipped.
_JS_MAX_PROFIT_DRAWDOWN_EXTRACTOR = """
    () => {
        const result = {};
        document.querySelectorAll(".brs-list").forEach(list => {
            const headline = list.querySelector(".brs-list__headline");
            if (!headline || headline.textContent.trim().toLowerCase() !== "info") return;
            list.querySelectorAll(".brs-list__entry").forEach(entry => {
                const labelElem = entry.querySelector("span");
                const valueElem = entry.querySelector("brs-widget-value");
                if (!labelElem || !valueElem) return;
                const label = labelElem.textContent.trim().toLowerCase();
                const value = valueElem.textContent.trim();
                if (label === "max profit") result["trading_max_profit"] = value;
                else if (label === "max drawdown") result["trading_max_drawdown"] = value;
            });
        });
        return result;
    }
"""

_JS_LEVERAGE_CHART_EXTRACTOR = """
    () => {
        // The series' actual attribute value has been observed as both
        // "chartxusedleveragelabel" and "chartxusedLeveragexlabel" (casing/"x"
        // separators vary), so match loosely on "leverage" appearing in the
        // attribute rather than pinning the exact string. It also lives on the
        // inner <g class="apexcharts-series"> (bearing seriesName), not the outer
        // <g class="apexcharts-bar-series"> wrapper -- so search any g[seriesName].
        const seriesG = Array.from(
            document.querySelectorAll("g[seriesName], g[seriesname]")
        ).find(g => /leverage/i.test(g.getAttribute("seriesName") || g.getAttribute("seriesname") || ""));
        if (!seriesG) return { bars: [], ticks: [] };

        const chartRoot = seriesG.closest("svg.apexcharts-svg") || seriesG.ownerSVGElement;
        if (!chartRoot) return { bars: [], ticks: [] };

        const ticks = Array.from(chartRoot.querySelectorAll(".apexcharts-xaxis-label"))
            .map(el => {
                const tspan = el.querySelector("tspan");
                return {
                    label: (tspan ? tspan.textContent : el.textContent).trim(),
                    x: parseFloat(el.getAttribute("x")),
                };
            })
            .filter(t => t.label);

        const bars = Array.from(seriesG.querySelectorAll("path.apexcharts-bar-area[val]"))
            .map(el => ({
                j: parseInt(el.getAttribute("j"), 10),
                val: el.getAttribute("val"),
                cx: parseFloat(el.getAttribute("cx")),
                barWidth: parseFloat(el.getAttribute("barWidth") || el.getAttribute("barwidth")),
            }))
            .filter(b => !Number.isNaN(b.j));

        return { bars, ticks };
    }
"""

_JS_INSTRUMENTS_EXTRACTOR = """
    () => {
        const result = {};
        document.querySelectorAll(".apexcharts-legend-series").forEach(series => {
            const symbol = series.getAttribute("seriesname") || series.getAttribute("seriesName");
            const textElem = series.querySelector(".apexcharts-legend-text");
            if (!symbol || !textElem) return;
            const match = textElem.textContent.trim().match(/:\\s*([\\d.,]+)\\s*$/);
            if (match) result[symbol] = match[1].replace(/,/g, "");
        });
        return result;
    }
"""

_JS_TRADE_STATS_EXTRACTOR = """
    () => {
        const result = {};
        document.querySelectorAll(".brs-list__entry").forEach(entry => {
            const spans = Array.from(entry.querySelectorAll("span"));
            const labelElem = spans.find(s => s.hasAttribute("transloco"));
            if (!labelElem) return;
            const label = labelElem.textContent.trim();
            const valueElem = spans.find(s => s !== labelElem && s.textContent.trim());
            if (valueElem) result[label] = valueElem.textContent.trim();
        });
        return result;
    }
"""

_EMPTY_METRICS: Dict[str, str] = {
    "return_total": "",
    "return_1d": "",
    "age_days": "",
    "return_all_time": "",
    "return_year": "",
    "return_half_year": "",
    "return_quarter": "",
    "return_month": "",
    "return_week": "",
    "return_day": "",
    "avg_return_weekly": "",
    "avg_return_monthly": "",
    "return_deviation": "",
    "return_deviation_monthly": "",
    "return_deviation_yearly": "",
    "monthly_chart": "",
    "trading_return_volatility_d": "",
    "trading_recovery_factor": "",
    "trading_absolute_gain": "",
    "trading_downside_deviation": "",
    "trading_sharpe_ratio": "",
    "trading_volatility_ratio": "",
    "trading_max_profit": "",
    "trading_max_drawdown": "",
    "leverage_chart": "",
    "instruments": "",
    "trade_statistics": "",
}


def _parse_month_tick_label(label: str) -> Optional[date]:
    """Parses an x-axis tick label like "Feb '26" into a date anchored at day 1 of that month."""
    match = re.match(r"^([A-Za-z]{3})\s*'?(\d{2})$", label.strip())
    if not match:
        return None
    month_str, yy = match.groups()
    month_num = _MONTH_ABBR_TO_NUM.get(month_str.lower())
    if not month_num:
        return None
    return date(2000 + int(yy), month_num, 1)


def compute_leverage_bar_dates(chart_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Reconstructs an approximate calendar date for each Leverage chart bar.

    The chart's x-axis is a true datetime axis: each bar's pixel width equals the
    axis's pixels-per-day scale (confirmed empirically against the provided sample
    markup), so a bar's date can be interpolated from its center-x pixel position
    relative to a known month-tick's x position.

    NOTE: this assumes each x-axis month tick is anchored at day 1 of that month
    (ApexCharts' typical default for a monthly-tick datetime axis). If that
    assumption is off, every reconstructed date will be off by the same constant
    number of days.
    """
    bars = chart_payload.get("bars") or []
    ticks = chart_payload.get("ticks") or []
    if not bars:
        return []

    parsed_ticks = []
    for t in ticks:
        d = _parse_month_tick_label(t.get("label", ""))
        x = t.get("x")
        if d is not None and x is not None:
            parsed_ticks.append((float(x), d))

    widths = sorted(
        b["barWidth"] for b in bars
        if isinstance(b.get("barWidth"), (int, float)) and b["barWidth"] == b["barWidth"]  # NaN != NaN
    )
    px_per_day = widths[len(widths) // 2] if widths else None  # median, robust to rounding noise

    results: List[Dict[str, Any]] = []
    for b in sorted(bars, key=lambda b: b.get("j", 0)):
        entry: Dict[str, Any] = {"value": b.get("val")}
        if parsed_ticks and px_per_day:
            ref_x, ref_date = parsed_ticks[0]
            cx = b.get("cx")
            if isinstance(cx, (int, float)) and cx == cx:  # NaN != NaN
                days_offset = round((float(cx) - ref_x) / px_per_day)
                entry["date"] = (ref_date + timedelta(days=days_offset)).isoformat()
        results.append(entry)

    return results


def _has_return_data(metrics: Dict[str, Any]) -> bool:
    return bool(metrics.get("return_total") or metrics.get("return_all_time"))


def _has_period_return_data(metrics: Dict[str, Any]) -> bool:
    # `return_total` (top summary) tends to render before the "Return/period"
    # indicator blocks (All time, Year, ...) finish binding, so checking for
    # it alone would let us stop polling too early. Check a period field
    # specifically to confirm those blocks are actually populated.
    return bool(metrics.get("return_all_time"))


def _has_trading_indicator_data(metrics: Dict[str, Any]) -> bool:
    return bool(
        metrics.get("trading_sharpe_ratio")
        or metrics.get("trading_recovery_factor")
        or metrics.get("trading_absolute_gain")
    )


def _has_bars(payload: Dict[str, Any]) -> bool:
    return bool(payload and payload.get("bars"))


def _dump_debug_snapshot(detail_page: Page, tag: str, profile_url: str) -> None:
    """
    Saves a screenshot + full HTML of `detail_page` under DEBUG_DIR when an
    expected extraction comes back empty after exhausting the poll window, so a
    failure can be diagnosed from what the bot actually saw instead of guessing.

    Gated behind DEBUG_SNAPSHOTS (see config.py) since this runs on every profile
    that comes back empty, which is noisy once the extractors are known-good.
    """
    if not DEBUG_SNAPSHOTS:
        return

    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        id_match = re.search(r"ratings/(\d+)", profile_url)
        trader_id = id_match.group(1) if id_match else "unknown"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = DEBUG_DIR / f"debug_{tag}_{trader_id}_{stamp}"

        detail_page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
        base.with_suffix(".html").write_text(detail_page.content(), encoding="utf-8")
        log.warning(f"Debug snapshot saved for {tag} (trader {trader_id}): {base.name}.png/.html")
    except Exception as e:
        log.debug(f"Failed to save debug snapshot ({tag}): {e}")


def scrape_trader_profile(detail_page: Page, profile_url: str) -> Dict[str, str]:
    """
    Navigates to a trader's profile URL on Tab 2 and extracts 'Return' tab metrics:
    - Top Summary: Return (total), Return (1D), Age (Days)
    - Return/period: All time, Year, Half year, Quarter, Month, Week, Day
    - Monthly: Average return (Weekly), Average return (Monthly), Return deviation, Return deviation (Monthly), Return deviation (Yearly)
    """
    metrics: Dict[str, str] = dict(_EMPTY_METRICS)

    if not profile_url:
        return metrics

    try:
        detail_page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
        random_sleep(1000, 1800)

        try:
            detail_page.wait_for_selector(
                ".ta-indicators_block, lib-profile-income-tab, .mat-tab-body-active, section.ta-indicators",
                timeout=12000,
            )
        except Exception:
            pass

        period_metrics = wait_for_evaluate(
            detail_page, _JS_INDICATORS_EXTRACTOR, _has_period_return_data, attempts=20, interval_ms=500
        )
        metrics.update(period_metrics)
        if not _has_period_return_data(period_metrics):
            _dump_debug_snapshot(detail_page, "return_period", profile_url)

        try:
            detail_page.wait_for_selector("path.apexcharts-bar-area", timeout=8000)
        except Exception:
            pass

        chart_data = wait_for_evaluate(detail_page, _JS_MONTHLY_CHART_EXTRACTOR, bool, attempts=6)
        if chart_data:
            metrics["monthly_chart"] = json.dumps(chart_data, ensure_ascii=False)

        # Switch to the 'Trading' tab for its own indicator blocks + Leverage chart
        if click_trading_tab(detail_page):
            random_sleep(500, 1000)

            # Re-run the same indicator extractor: the Trading tab's blocks share the
            # ta-indicators_block structure, just with different labels (Sharpe ratio,
            # Recovery factor, etc.) that are already handled above.
            trading_metrics = wait_for_evaluate(
                detail_page, _JS_INDICATORS_EXTRACTOR, _has_trading_indicator_data, attempts=20, interval_ms=500
            )
            metrics.update(trading_metrics)
            if not _has_trading_indicator_data(trading_metrics):
                _dump_debug_snapshot(detail_page, "trading_indicators", profile_url)

            max_pd_data = evaluate_with_frame_fallback(detail_page, _JS_MAX_PROFIT_DRAWDOWN_EXTRACTOR)
            if max_pd_data:
                metrics.update(max_pd_data)

            # Leverage bar chart: same ApexCharts bar pattern as the Monthly chart, but
            # at daily resolution across many bars rather than one bar per month, so we
            # reconstruct a per-bar date via compute_leverage_bar_dates() instead of a
            # simple index->label pairing.
            try:
                detail_page.wait_for_selector(
                    "g.apexcharts-bar-series[seriesName='chartxusedleveragelabel']",
                    timeout=8000,
                )
            except Exception:
                pass

            leverage_payload = evaluate_with_frame_fallback(detail_page, _JS_LEVERAGE_CHART_EXTRACTOR, _has_bars)
            if _has_bars(leverage_payload):
                leverage_bars = compute_leverage_bar_dates(leverage_payload)
                if leverage_bars:
                    metrics["leverage_chart"] = json.dumps(leverage_bars, ensure_ascii=False)

        # Switch to the 'Instruments' tab: donut legend (trade count per symbol,
        # assuming the "Count" toggle is the default view rather than "Volume")
        # plus the Trade Statistics list.
        if click_instruments_tab(detail_page):
            random_sleep(500, 1000)

            instruments_data = evaluate_with_frame_fallback(detail_page, _JS_INSTRUMENTS_EXTRACTOR)
            if instruments_data:
                metrics["instruments"] = json.dumps(instruments_data, ensure_ascii=False)

            trade_stats_data = evaluate_with_frame_fallback(detail_page, _JS_TRADE_STATS_EXTRACTOR)
            if trade_stats_data:
                metrics["trade_statistics"] = json.dumps(trade_stats_data, ensure_ascii=False)

    except Exception as e:
        log.warning(f"Notice reading profile ({profile_url}): {e}")

    return metrics
