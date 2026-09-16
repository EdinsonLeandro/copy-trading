import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from src.common.config import random_sleep
from src.common.logger import log
from src.common.playwright_utils import wait_for_evaluate
from src.brokers.binance.navigation import click_position_history_tab

# Binance's profile page is built from utility classes (Tailwind-style), with
# no stable component/BEM class names to key off. So instead of fixed
# selectors this matches by *shape*: a label element (class contains
# "t-caption1"/"t-body3") paired with a sibling/descendant value element
# (class contains "t-subtitle"), scoped to the row/container that holds both.
# This mirrors the "match by substring, not exact class" approach already
# used in fpmarkets/extractors.py for the same reason (the site ships
# different class variants for the same component).
_EXTRACT_PROFILE_JS = """
    () => {
        const norm = (s) => (s || "").replace(/\\s+/g, " ").trim();
        const hasClass = (el, token) => (el.className || "").includes(token);
        const fixPercentSpacing = (s) => norm(s).replace(/\\s+%/g, "%");

        // Trader name
        const nameEl = document.querySelector('h1[class*="t-headline5"]');
        const name = nameEl ? norm(nameEl.textContent) : "";

        // Trader level (e.g. "Legend"): a badge <img src="...badge-*.svg"> with
        // its level name in the following <span>.
        let level = "";
        const badgeImg = document.querySelector('img[src*="copytrading/badge"]');
        if (badgeImg && badgeImg.nextElementSibling) {
            level = norm(badgeImg.nextElementSibling.textContent);
        }

        // Trader description: the visible (non-"invisible") text-wrap block.
        // A hidden duplicate with the same classes exists purely for layout
        // measurement, so it must be excluded.
        let description = "";
        const descCandidates = Array.from(document.querySelectorAll("div")).filter(
            (d) => hasClass(d, "t-body3") && hasClass(d, "text-wrap") && !hasClass(d, "invisible"),
        );
        if (descCandidates.length > 0) description = norm(descCandidates[0].textContent);

        // Leverage + tags: the "tag-wrap" row holds one leverage tag (styled
        // with "text-TextLink") plus zero or more tags (styled with
        // "text-PrimaryText"). "TradFi" and "API Trading" are account-type
        // flags every trader either has or doesn't, so they're split out as
        // booleans; everything else (Top Performer, Money Maker, Most
        // Resilient, Whale Manager, Solid Growth, Low Leverage, ...) is a
        // genuine achievement tag and goes into the `tags` list.
        let leverage = "";
        let tradfi = false;
        let apiTrading = false;
        const tags = [];
        const tagWrap = Array.from(document.querySelectorAll("div")).find((d) => hasClass(d, "tag-wrap"));
        if (tagWrap) {
            const tagEls = Array.from(tagWrap.querySelectorAll("div")).filter(
                (d) => hasClass(d, "t-caption1") && hasClass(d, "cursor-help"),
            );
            for (const tagEl of tagEls) {
                const text = norm(tagEl.textContent);
                if (!text) continue;
                if (hasClass(tagEl, "text-TextLink") || /leverage/i.test(text)) {
                    leverage = text;
                } else if (text === "TradFi") {
                    tradfi = true;
                } else if (text === "API Trading") {
                    apiTrading = true;
                } else {
                    tags.push(text);
                }
            }
        }

        // Stat blocks: Days Trading / Copiers / Total Copiers / Mock Copiers /
        // Closed Portfolios. Each is a container holding a "t-caption1" label
        // and a "t-subtitle*" value (sometimes nested one level deeper, e.g.
        // Copiers' value sits inside its own wrapper div). Observed: when a
        // stat is genuinely 0, Binance sometimes omits the value element
        // entirely instead of rendering "0" (Mock Copiers in particular) - so
        // readiness is judged by the LABEL rendering, not the value, and a
        // missing value next to a present label is treated as "0" rather
        // than "still loading".
        const stats = {};
        const statContainers = Array.from(document.querySelectorAll("div")).filter(
            (d) => hasClass(d, "mobile:flex-col") && hasClass(d, "items-center") && hasClass(d, "gap-[2px]"),
        );
        for (const container of statContainers) {
            const label = container.querySelector('[class*="t-caption1"]');
            if (!label) continue;
            const value = container.querySelector('[class*="t-subtitle"]');
            stats[norm(label.textContent)] = value ? norm(value.textContent) : "0";
        }

        // "Mock Copy" action button: present only for portfolios still open
        // to copying.
        const mockCopyAvailable = Array.from(document.querySelectorAll("button")).some(
            (b) => norm(b.textContent) === "Mock Copy",
        );

        // Asset Preferences donut legend: each entry is a swatch + a
        // "SYMBOL value%" text block (symbol/value/"%" are separate text
        // nodes that norm() collapses to single spaces, so the symbol is
        // everything before the last space and the percentage is after it).
        const assetPreferences = {};
        const legendItems = Array.from(document.querySelectorAll("div")).filter(
            (d) => hasClass(d, "w-[150px]") && hasClass(d, "h-[42px]") && hasClass(d, "hover:bg-Vessel"),
        );
        for (const item of legendItems) {
            const textEl = item.querySelector('[class*="t-caption3"], [class*="t-subtitle3"]');
            if (!textEl) continue;
            const raw = fixPercentSpacing(textEl.textContent);
            const spaceIdx = raw.lastIndexOf(" ");
            if (spaceIdx <= 0) continue;
            const symbol = raw.slice(0, spaceIdx);
            const pct = raw.slice(spaceIdx + 1);
            if (symbol && pct) assetPreferences[symbol] = pct;
        }

        // Performance panel. ROI/PnL are a special case: one row holds both
        // labels side by side, the next sibling row holds both "t-subtitle1"
        // values side by side (same order). Every other metric (Copier PnL,
        // Sharpe Ratio, MDD, Win Rate, Win Positions, Total Positions) is a
        // single label("t-body3")/value("t-subtitle2") pair per row.
        const perf = {};

        const labelRows = Array.from(document.querySelectorAll("div")).filter(
            (d) => hasClass(d, "justify-between") && hasClass(d, "mb-[4px]"),
        );
        for (const row of labelRows) {
            const labels = Array.from(row.querySelectorAll('[class*="t-body3"]')).map((e) => norm(e.textContent));
            const valueRow = row.nextElementSibling;
            if (!valueRow) continue;
            const values = Array.from(valueRow.querySelectorAll('[class*="t-subtitle1"]')).map((e) =>
                fixPercentSpacing(e.textContent),
            );
            labels.forEach((label, i) => {
                if (label && values[i] !== undefined) perf[label] = values[i];
            });
        }

        const singleRows = Array.from(document.querySelectorAll("div")).filter(
            (d) => hasClass(d, "justify-between") && hasClass(d, "py-[8px]"),
        );
        for (const row of singleRows) {
            const label = row.querySelector('[class*="t-body3"]');
            const value = row.querySelector('[class*="t-subtitle2"]');
            if (!label || !value) continue;
            const labelText = norm(label.textContent);
            if (labelText) perf[labelText] = fixPercentSpacing(value.textContent);
        }

        return {
            name,
            level,
            description,
            leverage,
            tradfi,
            api_trading: apiTrading,
            tags,
            days_trading: stats["Days Trading"] || "",
            copiers: stats["Copiers"] || "",
            total_copiers: stats["Total Copiers"] || "",
            mock_copiers: stats["Mock Copiers"] || "",
            closed_portfolios: stats["Closed Portfolios"] || "",
            mock_copy_available: mockCopyAvailable,
            roi: perf["ROI"] || "",
            pnl: perf["PnL"] || "",
            copier_pnl: perf["Copier PnL"] || "",
            sharpe_ratio: perf["Sharpe Ratio"] || "",
            mdd: perf["MDD"] || "",
            win_rate: perf["Win Rate"] || "",
            win_positions: perf["Win Positions"] || "",
            total_positions: perf["Total Positions"] || "",
            // Lead Trader Overview panel: same label/value row shape as the
            // Performance metrics above, so it's picked up by the same
            // singleRows pass into `perf`.
            aum: perf["AUM"] || "",
            profit_sharing: perf["Profit Sharing"] || "",
            leading_margin_balance: perf["Leading Margin Balance"] || "",
            lock_up_period: perf["Lock-up period"] || "",
            minimum_copy_amount: perf["Minimum Copy Amount"] || "",
            asset_preferences: assetPreferences,
        };
    }
"""


# All stat-row fields, checked together with name/roi/pnl below. Observed in
# practice: "Mock Copiers" can render a beat after the rest of this row (and
# after name/ROI/PnL are already visible), so checking only name+roi/pnl let
# scrape_trader_profile occasionally accept a snapshot with this field still
# blank.
_STAT_ROW_FIELDS = ("days_trading", "copiers", "total_copiers", "mock_copiers", "closed_portfolios")


def _is_profile_data_loaded(result: Any) -> bool:
    if not result or not result.get("name"):
        return False
    if not (result.get("roi") or result.get("pnl")):
        return False
    # "aum" stands in for the whole Lead Trader Overview panel: it's on the
    # same label/value row shape as the Performance metrics, so if it's
    # populated the rest of that panel (profit_sharing, lock_up_period, ...)
    # should be too.
    if not result.get("aum"):
        return False
    return all(result.get(field) for field in _STAT_ROW_FIELDS)


# Each row is a symbol + tag chips ("Perp", "6X", "Cross Long", ...) + a
# status ("Closed") + a variable set of label/value fields (Opened, Entry
# Price, Max. Open Interest, Closing PNL, Closed, Avg. Close Price, Closed
# Vol., ...). The field set is collected generically (whatever labels are
# actually present) rather than pinned to a fixed list, since different
# position types (e.g. margin vs futures, long vs short) are expected to
# show different fields.
_EXTRACT_POSITION_HISTORY_JS = """
    () => {
        const norm = (s) => (s || "").replace(/\\s+/g, " ").trim();
        const hasClass = (el, token) => (el.className || "").includes(token);

        const rows = Array.from(document.querySelectorAll("tr.bn-web-table-row"));
        const positions = [];

        for (const row of rows) {
            // Binance's table renders one invisible row purely to measure
            // row height; it holds no position data.
            if (hasClass(row, "bn-web-table-measure-row")) continue;

            const cell = row.querySelector("td.bn-web-table-cell");
            if (!cell) continue;

            const symbolEl = cell.querySelector('[class*="t-subtitle1"]');
            const symbol = symbolEl ? norm(symbolEl.textContent) : "";
            if (!symbol) continue;

            const tags = Array.from(cell.querySelectorAll(".bn-tag-wrap .bn-bubble-content"))
                .map((el) => norm(el.textContent))
                .filter(Boolean);

            const statusEl = cell.querySelector('[class*="t-body3"][class*="text-PrimaryText"]');
            const status = statusEl ? norm(statusEl.textContent) : "";

            const fields = {};
            const labelEls = Array.from(cell.querySelectorAll('[class*="t-caption2"][class*="text-SecondaryText"]'));
            for (const labelEl of labelEls) {
                const label = norm(labelEl.textContent);
                if (!label) continue;
                const valueEl = labelEl.nextElementSibling;
                fields[label] = valueEl ? norm(valueEl.textContent) : "";
            }

            positions.push({ symbol, tags, status, fields });
        }

        return positions;
    }
"""


def scrape_position_history(detail_page: Page) -> List[Dict[str, Any]]:
    """Switches a trader's profile page to the 'Position History' tab and
    extracts every row (this table isn't virtualized, so one pass covers
    all of them - see click_position_history_tab)."""
    if not click_position_history_tab(detail_page):
        log.debug("Could not switch to Position History tab.")
        return []

    random_sleep(800, 1500)

    rows = wait_for_evaluate(
        detail_page,
        _EXTRACT_POSITION_HISTORY_JS,
        is_sufficient=lambda r: bool(r),
        attempts=12,
        interval_ms=500,
    )
    return rows or []


def _is_roi_chart_response(response: Any, portfolio_id: str) -> bool:
    url = response.url
    if "chart-data" not in url or "dataType=ROI" not in url:
        return False
    return not portfolio_id or f"portfolioId={portfolio_id}" in url


def _capture_roi_chart_data(detail_page: Page, profile_url: str, portfolio_id: str) -> Optional[Any]:
    """Navigates to `profile_url` while listening for the ROI chart's own
    `chart-data` XHR (dataType=ROI), and returns its parsed JSON payload.

    This is the raw series data the chart is drawn from, so it's a far more
    reliable source than the rendered <path> - the SVG only carries a pixel
    curve, not the underlying values/dates. `expect_response` is set up
    before `goto` (as its context manager) so the request can't fire and be
    missed before the listener is armed.
    """
    try:
        with detail_page.expect_response(
            lambda r: _is_roi_chart_response(r, portfolio_id), timeout=20000
        ) as response_info:
            detail_page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        return response_info.value.json()
    except Exception as e:
        log.debug(f"Could not capture ROI chart-data response for {profile_url}: {e}")
        return None


def _parse_roi_chart_payload(raw: Any) -> List[Dict[str, Any]]:
    """Reshapes the chart-data response's {"data": [{"value", "dataType",
    "dateTime"}, ...]} envelope into a plain [{"date", "value"}, ...] list:
    `dateTime` is epoch milliseconds (converted to a "YYYY-MM-DD" date), and
    `dataType` is dropped since it's always "ROI" here."""
    if not isinstance(raw, dict):
        return []

    points = []
    for entry in raw.get("data") or []:
        if not isinstance(entry, dict) or entry.get("dateTime") is None:
            continue
        date_str = datetime.fromtimestamp(entry["dateTime"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        points.append({"date": date_str, "value": entry.get("value")})

    return points


def scrape_trader_profile(detail_page: Page, profile_url: str) -> Dict[str, Any]:
    """Navigates to a trader's Copy Trading profile page and extracts the
    fields described in the profile UI (name, level, tags, performance
    metrics, etc). Polls after navigation since the SPA renders the panel
    client-side after the DOM shell is present."""
    log.debug(f"Navigating to profile: {profile_url}")

    id_match = re.search(r"lead-details/(\d+)", profile_url)
    portfolio_id = id_match.group(1) if id_match else ""

    roi_chart_data = _capture_roi_chart_data(detail_page, profile_url, portfolio_id)
    random_sleep(1000, 2000)

    result = wait_for_evaluate(
        detail_page,
        _EXTRACT_PROFILE_JS,
        is_sufficient=_is_profile_data_loaded,
        attempts=16,
        interval_ms=600,
    ) or {}

    result["tags"] = json.dumps(result.get("tags") or [], ensure_ascii=False)
    result["asset_preferences"] = json.dumps(result.get("asset_preferences") or {}, ensure_ascii=False)
    result["roi_chart"] = json.dumps(_parse_roi_chart_payload(roi_chart_data), ensure_ascii=False)
    result["position_history"] = json.dumps(scrape_position_history(detail_page), ensure_ascii=False)
    return result
