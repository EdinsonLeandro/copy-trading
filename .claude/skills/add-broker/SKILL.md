---
name: add-broker
description: Add a new broker (e.g. OKX, Bybit) to the copy-trading scraper by creating a src/brokers/<name>/ package with the standard two-phase shape and wiring it into main.py. Use when the user asks to support, add or scaffold a new broker or platform.
---

# Add a new broker

Goal: a new `src/brokers/<name>/` package that behaves exactly like `binance/` and `fpmarkets/`, so `python main.py --broker <name>` runs Phase 1 (collect profile URLs) then Phase 2 (scrape each profile).

## 0. Gather facts first

Ask the user for anything you can't find yourself:
- Broker name (lowercase, used as folder, `.env` prefix, `data/<name>/`, `auth_state/<name>.json`).
- Login URL, how login works (email/password, PIN, captcha, app-push approval), and the URL of the copy-trading leaderboard.
- Which fields on a trader's profile page they want. Ask for saved HTML of a leaderboard page and a profile page if available; don't guess selectors.

Don't log into the live site to explore without the user's OK.

## 1. Copy the closest existing broker

Use `src/brokers/binance/` as the template for SPA sites with utility-class markup and network data, `src/brokers/fpmarkets/` for Angular Material / iframe-style pages. Read the template's modules fully before writing.

Create these files, each with the same responsibilities as the template:

| File | Contents |
|---|---|
| `__init__.py` | Empty. |
| `config.py` | `BROKER_NAME`, credentials from `os.getenv("<NAME>_...")`, URLs, `DATA_DIR`/`DEBUG_DIR`/`AUTH_STATE_PATH` under the shared dirs, Phase 1 CSV path + `.done` marker path, `TRADER_DETAILS_CSV_PATH`, `ensure_directories()`, `validate_credentials()`. No side effects at import. |
| `auth.py` | `perform_login(page) -> bool`, `is_session_valid(page) -> bool`, and `get_authenticated_session(force_fresh_login)` that delegates to `src.common.browser_session.get_authenticated_session`. Type with `human_type`, pause with `random_sleep`. |
| `csv_schema.py` | Phase 1 headers + `*_ID_FIELDS`, `TRADER_DETAILS_CSV_HEADERS` + `TRADER_DETAILS_ID_FIELDS`. Comment each JSON column with an example value. |
| `navigation.py` | Open the leaderboard, read page info, extract cards (ID + profile URL), `is_next_button_disabled`, `click_next_page`, tab-switch helpers for the profile page. |
| `extractors.py` | `scrape_trader_profile(page, profile_url) -> dict`, JS extraction scripts, `_dump_debug_snapshot`, `_maybe_human_scroll`. |
| `orchestrator.py` | Phase 1 `scrape_all_<x>_urls`, `is_<x>_url_collection_complete`, `reset_all_data`, `clear_debug_snapshots`, Phase 2 `scrape_all_trader_details` returning `TraderDetailsSummary`. |
| `run.py` | `run(force_fresh_login=False)`: `log.set_label`, `ensure_directories`, `RESTART_FROM_SCRATCH` reset, `clear_debug_snapshots`, auth, both phases with summary panels, `close_browser_session` in `finally`. |

## 2. Rules the new broker must follow

- `src/common/` stays broker-agnostic. If you need a new shared helper, make it generic; broker-specific logic stays in the package.
- Phase 1 appends each page's new rows immediately and writes the `.done` marker only on the true last page (not on a `max_pages` stop).
- Phase 2: skip IDs already in `trader_details.csv`, append one row per profile right away, cap the run at `random.randint(SESSION_CAP_MIN, SESSION_CAP_MAX)`, take a long break every `LONG_BREAK_EVERY_MIN`-`MAX` profiles, `random_sleep(MIN_DELAY_MS, MAX_DELAY_MS)` otherwise.
- Errors: `scrape_trader_profile` must not swallow navigation errors. In the orchestrator, `PlaywrightTimeoutError` → log and re-raise (abort run); any other exception → log and `continue` (profile not saved, retried next run).
- Polling: use `wait_for_evaluate` with an `is_sufficient` check that waits for the slowest-rendering field, and call `_dump_debug_snapshot` when it still comes back incomplete.
- Prefer matching selectors by class substring or by structure over exact class names; capture chart data from network responses (`expect_response`) when the site exposes it.
- Store values as displayed text; JSON-encode nested data with `json.dumps(..., ensure_ascii=False)`.
- Log with `src.common.logger.log`, never `print`.

## 3. Wire it up

- `main.py`: import `run` as `run_<name>` and add it to `BROKER_RUNNERS`.
- `.env.example` and the README `.env` block: add a `# --- <Broker> credentials ---` section.
- README: add the package to the project tree and mention its Phase 1 CSV / marker in "Run a Scraper" and "Key Features".
- `docs/data-dictionary.md`: add a section for both CSVs and a column in the "Comparing brokers" table.

## 4. Tests

Add `tests/<name>/__init__.py` and unit tests for every pure function (page-label parsing, date/number reconstruction, payload reshaping), using small fake locator classes like `tests/fpmarkets/test_navigation.py`. Run `pytest` and make sure everything passes.

## 5. Hand-off

Don't run the scraper yourself. Tell the user to run `python main.py --broker <name>` with `HEADLESS=False` and `DEBUG_SNAPSHOTS=True` for the first run, and suggest a small first run (e.g. `SESSION_CAP_MIN=SESSION_CAP_MAX=5`). List any selectors you couldn't verify.
