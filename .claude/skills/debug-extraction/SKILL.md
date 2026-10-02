---
name: debug-extraction
description: Diagnose and fix scraper fields that come back empty or wrong (blank CSV columns, missing JSON data, "Debug snapshot saved" warnings, timeouts) for any broker. Use when the user reports missing/incorrect scraped data or a broken extractor after a site change.
---

# Debug an extraction problem

Work from evidence (logs, snapshots, saved HTML), not guesses. The site's markup is the source of truth.

## 1. Pin down the symptom

Find out:
- Broker, and which column(s) are empty or wrong.
- All profiles or only some? Since when? (A sudden change across all profiles usually means the site changed its markup.)
- One or two example `profile_url`s.

Check the logs: `logs/latest_<broker>.log` (most recent run) or `logs/run_<broker>_<timestamp>.log`. Look for:
- `Debug snapshot saved for <tag>`: an extraction came back incomplete.
- `Timeout while scraping profile`: the run aborted. This is usually throttling, not a selector problem; suggest waiting, a smaller `SESSION_CAP_*`, or longer delays rather than changing code.
- `Failed to scrape profile`: an exception on one profile; read the message.

Read only the log lines you need. Don't open `.env` or `auth_state/`.

## 2. Get a snapshot of what the bot saw

Snapshots are only written when `DEBUG_SNAPSHOTS=True`. If `debug/<broker>/` is empty, ask the user to set it and re-run (a small run is enough: `SESSION_CAP_MIN=SESSION_CAP_MAX=3`). Snapshots are cleared at the start of each run.

Files are `debug/<broker>/debug_<tag>_<id>_<timestamp>.png` + `.html`. Tags map to code:

| Broker | Tag | Covers |
|---|---|---|
| fpmarkets | `return_period` | `_JS_INDICATORS_EXTRACTOR` on the Return tab (return_* / avg_* / deviation fields) |
| fpmarkets | `trading_indicators` | same extractor on the Trading tab (trading_* fields) |
| binance | `profile_fields` | `_EXTRACT_PROFILE_JS` (name, stats, performance, overview, asset_preferences) |
| binance | `position_history_tab` / `position_history_rows` | tab didn't render / rows not extracted |
| binance | `copy_traders_tab` / `copy_traders_rows` | tab had no rows / a page came back empty |

Fields without a snapshot tag (FP Markets `monthly_chart`, `leverage_chart`, `instruments`, `trade_statistics`, `trading_max_*`; Binance `roi_chart`) just stay empty; inspect them with the user's saved HTML or the test script.

## 3. Find the cause

Open the `.png` first (is the page logged in, loaded, on the right tab?), then search the `.html` for the field's label text and compare the surrounding markup with the selectors in `src/brokers/<broker>/extractors.py` (and tab helpers in `navigation.py`). Common causes:

1. **Markup changed:** class names/structure differ from the selector. Fix by matching more loosely (class substring, label text, structure), in line with the comments already in the extractor.
2. **Rendered too late:** the field is present in the HTML but the poll stopped early. Make the `is_sufficient` check (`_has_*` / `_is_profile_data_loaded`) wait for that field, or raise `attempts`.
3. **Wrong scope:** a selector matched a different chart/tab/list (hidden tab panes stay mounted; several charts share classes). Scope to the active pane or a specific container ID.
4. **Label text changed:** update the label match (keep the old one too if both variants appear).
5. **Network data:** for `roi_chart`, check the `_is_roi_chart_response` URL filter still matches the request.
6. **Not a bug:** private portfolio, zero copiers, or the site genuinely hides the value (see `docs/data-dictionary.md`).

## 4. Fix

- Smallest change in the broker's `extractors.py` / `navigation.py`; keep the existing error-handling rules (don't catch navigation errors inside `scrape_trader_profile`).
- If the fix applies to a pure Python helper (parsing, date reconstruction, payload reshaping), add or update a test in `tests/<broker>/` and run `pytest`.
- Add a short comment explaining the site quirk, matching existing comment style.
- If a column's meaning or format changed, update `csv_schema.py` comments and `docs/data-dictionary.md`.

## 5. Verify

Don't run against the live site yourself; ask the user. Options:
- Binance: `python scripts/test_profile_extractor/test_binance_profile_extractor.py <profile_url> ...` writes results to `scripts/test_profile_extractor/binance_profile_extractor_test_results.csv` for comparison with the browser.
- Any broker: a short run with `DEBUG_SNAPSHOTS=True` and a small `SESSION_CAP_*`.

Rows already saved with blank fields are not rescraped automatically (deduplication). Tell the user: either remove those rows from `data/<broker>/trader_details.csv` so they're retried, or use `RESTART_FROM_SCRATCH=True` for a full rescrape.
