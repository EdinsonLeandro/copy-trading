from src.scraper.extractors import _parse_month_tick_label, compute_leverage_bar_dates


def test_parse_month_tick_label_valid():
    assert _parse_month_tick_label("Feb '26").isoformat() == "2026-02-01"


def test_parse_month_tick_label_no_quote():
    assert _parse_month_tick_label("Feb 26").isoformat() == "2026-02-01"


def test_parse_month_tick_label_invalid_returns_none():
    assert _parse_month_tick_label("not a label") is None


def test_compute_leverage_bar_dates_empty_bars_returns_empty_list():
    assert compute_leverage_bar_dates({"bars": [], "ticks": []}) == []


def test_compute_leverage_bar_dates_without_ticks_returns_values_only():
    payload = {
        "bars": [{"j": 0, "val": "5", "cx": 10, "barWidth": 2}],
        "ticks": [],
    }
    result = compute_leverage_bar_dates(payload)
    assert result == [{"value": "5"}]


def test_compute_leverage_bar_dates_interpolates_from_tick():
    # One tick anchored at Jan 1 2026, x=0; bars spaced 1 day apart (barWidth=1px/day).
    payload = {
        "bars": [
            {"j": 0, "val": "1", "cx": 0, "barWidth": 1},
            {"j": 1, "val": "2", "cx": 5, "barWidth": 1},
        ],
        "ticks": [{"label": "Jan '26", "x": 0}],
    }
    result = compute_leverage_bar_dates(payload)
    assert result[0] == {"value": "1", "date": "2026-01-01"}
    assert result[1] == {"value": "2", "date": "2026-01-06"}


def test_compute_leverage_bar_dates_sorts_by_bar_index():
    payload = {
        "bars": [
            {"j": 1, "val": "2", "cx": 5, "barWidth": 1},
            {"j": 0, "val": "1", "cx": 0, "barWidth": 1},
        ],
        "ticks": [],
    }
    result = compute_leverage_bar_dates(payload)
    assert [r["value"] for r in result] == ["1", "2"]
