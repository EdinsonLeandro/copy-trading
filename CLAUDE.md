# CLAUDE.md

A Playwright (Patchright fork) scraper that logs into broker portals (FP Markets, Binance) and saves public copy-trading leader statistics to CSV. It does not place trades. See @README.md for setup and the full project layout.

## Commands

```bash
.\.venv\Scripts\Activate.ps1          # Windows; activate the venv first
pip install -r requirements.txt          # drives installed Google Chrome via Patchright
python main.py --broker fpmarkets     # or: binance
python main.py --broker binance --force-fresh-login
pytest                                # unit tests (no browser needed)
```

## Architecture

- Import from `patchright.sync_api`, never `playwright.sync_api`: Patchright raises its own `TimeoutError` class, so a mixed import silently breaks the Phase 2 timeout abort.
- `src/common/` must stay broker-agnostic: no broker names, URLs or data fields. Shared helpers: `browser_session.py` (launch, saved sessions, `close_browser_session`), `playwright_utils.py` (`evaluate_with_frame_fallback`, `wait_for_evaluate`, `click_tab`), `csv_store.py` (`init_csv_file`, `append_rows`, `load_existing_ids`), `config.py` (env settings, `random_sleep`), `logger.py` (`log`), `scrape_summary.py`.
- Each broker in `src/brokers/<name>/` has the same modules: `config`, `auth`, `csv_schema`, `navigation`, `extractors`, `orchestrator`, `run`. Keep binance and fpmarkets symmetrical; when changing one, check whether the other needs the same change.
- New broker = new package with that shape + register its `run()` in `BROKER_RUNNERS` in `main.py`.

## Two-phase pipeline (both brokers)

1. **Phase 1** paginates the leaderboard and saves profile URLs (`data/<broker>/portfolio_urls.csv` or `leader_urls.csv`). When it reaches the true last page it writes a `.done` marker so later runs skip Phase 1.
2. **Phase 2** visits each URL not yet in `data/<broker>/trader_details.csv`, scrapes it and appends one row immediately. Each run stops after a random `SESSION_CAP_MIN`-`SESSION_CAP_MAX` profiles and returns a `TraderDetailsSummary`.

Invariants to preserve:
- Write each row as soon as it's scraped (resumable, no duplicates via the schema's `*_ID_FIELDS`).
- In Phase 2, a Playwright `TimeoutError` aborts the run (the site is probably throttling). Any other error skips that profile without saving, so it's retried next run. Extractors must not swallow these errors.
- Keep the anti-detection pacing (`random_sleep`, long breaks, session cap). Don't remove or shorten it to speed things up.

## Conventions

- Log through `from src.common.logger import log` (`info`/`success`/`warning`/`error`/`debug`, `log.print` for rich panels), never `print`.
- New settings: read in `src/common/config.py` (shared) or the broker's `config.py`, and add them to both `.env.example` and the README's `.env` block.
- CSV columns live only in the broker's `csv_schema.py`. Changing headers breaks existing CSVs in `data/`; mention this when you do it.
- Comments explain *why* (site quirks, timing reasons); match the existing docstring style.

## Testing

- `pytest` covers pure logic only (CSV store, pagination-label parsing, date reconstruction), using small fake locator classes instead of a browser (see `tests/fpmarkets/test_navigation.py`). Add tests the same way for new pure functions.
- Scraping and login can only be checked against the live sites. **Ask before running `main.py` or anything in `scripts/`**: they log into real accounts, may need manual captcha/2FA, and count against rate limits.

## Don'ts

- Never open, read, print or edit `.env` or anything in `auth_state/` (real credentials and session cookies), by any means including shell commands. `.env.example` may be read and edited. If you need to know which settings exist, read `.env.example` or `src/common/config.py`.
- Never commit `.env`, `auth_state/`, `data/`, `debug/` or `logs/`.
- Don't edit `analysis/` notebooks unless asked; they have their own `analysis/requirements.txt`.
