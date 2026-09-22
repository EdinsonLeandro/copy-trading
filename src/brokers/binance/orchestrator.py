import csv
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import Page

from src.common.config import DEBUG_SNAPSHOTS, random_sleep
from src.common.csv_store import append_rows, init_csv_file, load_existing_ids
from src.common.logger import log
from src.brokers.binance.config import (
    DEBUG_DIR,
    PORTFOLIO_URLS_CSV_PATH,
    PORTFOLIO_URLS_DONE_MARKER,
    TRADER_DETAILS_CSV_PATH,
)
from src.brokers.binance.csv_schema import (
    PORTFOLIO_URLS_CSV_HEADERS,
    PORTFOLIO_URLS_ID_FIELDS,
    TRADER_DETAILS_CSV_HEADERS,
    TRADER_DETAILS_ID_FIELDS,
)
from src.brokers.binance.extractors import scrape_trader_profile
from src.brokers.binance.navigation import (
    click_next_page,
    disable_smart_filter,
    extract_portfolio_cards,
    is_next_button_disabled,
    navigate_to_copy_trading,
    parse_pagination_info,
    select_all_portfolios_tab,
    select_time_range,
)


def scrape_all_portfolio_urls(page: Page, max_pages: Optional[int] = None) -> int:
    """
    Collects every trader's Copy Trading profile URL from the leaderboard
    (All Portfolios, 365 Days, Smart Filter off), paginating until the Next
    button is disabled.

    Resumable: URLs already saved in a previous run are loaded up front and
    skipped, and each page's new URLs are appended to CSV and flushed
    immediately, so an interrupted run (there are 12K+ profiles) can be
    restarted without re-scraping pages already covered.
    """
    init_csv_file(PORTFOLIO_URLS_CSV_PATH, PORTFOLIO_URLS_CSV_HEADERS)
    seen_ids = load_existing_ids(PORTFOLIO_URLS_CSV_PATH, PORTFOLIO_URLS_ID_FIELDS)
    log.info(f"Loaded {len(seen_ids)} existing portfolio URLs from {PORTFOLIO_URLS_CSV_PATH.name}")

    navigate_to_copy_trading(page)
    select_all_portfolios_tab(page)
    select_time_range(page, "365 Days")
    disable_smart_filter(page)

    page_idx = 1
    total_saved = 0

    while True:
        curr_page, total_pages = parse_pagination_info(page)
        display_page = curr_page if curr_page > 0 else page_idx
        display_total = total_pages if total_pages > 0 else "?"

        cards = extract_portfolio_cards(page, display_page)
        log.info(f"─── Page {display_page}/{display_total}: Found {len(cards)} portfolios on page ───")

        new_rows = []
        for card in cards:
            pid = card["portfolio_id"]
            purl = card["profile_url"]

            if (pid and pid in seen_ids) or (purl and purl in seen_ids):
                continue

            row = {
                **card,
                "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            new_rows.append(row)
            if pid:
                seen_ids.add(pid)
            if purl:
                seen_ids.add(purl)

        if new_rows:
            append_rows(new_rows, PORTFOLIO_URLS_CSV_PATH, PORTFOLIO_URLS_CSV_HEADERS)
            total_saved += len(new_rows)
            log.success(f"✓ Saved {len(new_rows)} new portfolio URLs (Total saved: {total_saved})")
        else:
            log.debug("No new portfolio URLs on this page (already scraped).")

        if max_pages and display_page >= max_pages:
            log.warning(f"Reached requested max pages limit ({max_pages}). Stopping.")
            break

        if is_next_button_disabled(page):
            log.success("Next button is disabled. Reached the last page.")
            PORTFOLIO_URLS_DONE_MARKER.write_text(
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8"
            )
            break

        log.info(f"Advancing to page {display_page + 1}...")
        click_next_page(page)
        random_sleep(600, 1200)
        page_idx += 1

    log.success(f"✓ Portfolio URL collection complete! All URLs saved in: {PORTFOLIO_URLS_CSV_PATH}")
    return total_saved


def is_portfolio_url_collection_complete() -> bool:
    """True once scrape_all_portfolio_urls has reached the true last page in
    a prior run (see PORTFOLIO_URLS_DONE_MARKER) - lets a rerun skip
    straight to phase 2 instead of re-paginating the whole leaderboard."""
    return PORTFOLIO_URLS_DONE_MARKER.exists()


def reset_all_data() -> None:
    """Deletes every previous-run output (both phases' CSVs and the phase-1
    completion marker) so the pipeline restarts from a clean slate. Only
    called when RESTART_FROM_SCRATCH is set; normal runs resume instead.

    Does NOT touch debug/binance/ - see clear_debug_snapshots(), which is
    gated on DEBUG_SNAPSHOTS alone and called independently of this flag."""
    for path in (PORTFOLIO_URLS_CSV_PATH, TRADER_DETAILS_CSV_PATH, PORTFOLIO_URLS_DONE_MARKER):
        if path.exists():
            path.unlink()
            log.warning(f"RESTART_FROM_SCRATCH: deleted {path}")


def clear_debug_snapshots() -> None:
    """Deletes any screenshot/HTML dumps left in debug/binance/ from a prior
    run. Called whenever DEBUG_SNAPSHOTS is on, independent of
    RESTART_FROM_SCRATCH, so stale snapshots from an earlier run don't get
    mixed up with the current one's."""
    if not (DEBUG_SNAPSHOTS and DEBUG_DIR.exists()):
        return

    deleted = 0
    for f in DEBUG_DIR.iterdir():
        if f.is_file():
            f.unlink()
            deleted += 1
    if deleted:
        log.info(f"Cleared {deleted} debug snapshot file(s) from a previous run in {DEBUG_DIR}")


def _load_portfolio_urls() -> list:
    if not PORTFOLIO_URLS_CSV_PATH.exists():
        return []
    with open(PORTFOLIO_URLS_CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {"portfolio_id": row.get("portfolio_id", ""), "profile_url": row.get("profile_url", "")}
            for row in reader
            if row.get("profile_url")
        ]


def scrape_all_trader_details(page: Page, max_profiles: Optional[int] = None) -> int:
    """
    Phase 2: visits every profile URL collected by scrape_all_portfolio_urls
    (PORTFOLIO_URLS_CSV_PATH) and scrapes its full detail-page data via
    scrape_trader_profile, saving each result to TRADER_DETAILS_CSV_PATH.

    Resumable: traders already saved in a previous run are loaded up front and
    skipped, and each profile's result is appended to CSV and flushed
    immediately, so an interrupted run can be restarted without re-scraping
    profiles already covered. One profile failing to scrape is logged and
    skipped rather than aborting the whole run.
    """
    portfolios = _load_portfolio_urls()
    if not portfolios:
        log.warning(f"No portfolio URLs found in {PORTFOLIO_URLS_CSV_PATH.name}. Run phase 1 first.")
        return 0

    init_csv_file(TRADER_DETAILS_CSV_PATH, TRADER_DETAILS_CSV_HEADERS)
    seen_ids = load_existing_ids(TRADER_DETAILS_CSV_PATH, TRADER_DETAILS_ID_FIELDS)
    log.info(f"Loaded {len(seen_ids)} existing trader details from {TRADER_DETAILS_CSV_PATH.name}")

    remaining = [
        p for p in portfolios
        if p["portfolio_id"] not in seen_ids and p["profile_url"] not in seen_ids
    ]
    log.info(f"{len(remaining)} of {len(portfolios)} profiles remain to be scraped.")

    if max_profiles:
        remaining = remaining[:max_profiles]

    total_saved = 0
    for i, portfolio in enumerate(remaining, start=1):
        profile_url = portfolio["profile_url"]
        log.info(f"─── Profile {i}/{len(remaining)}: {profile_url} ───")

        try:
            result = scrape_trader_profile(page, profile_url)
        except Exception as e:
            log.error(f"Failed to scrape profile {profile_url}: {e}")
            continue

        row = {
            "portfolio_id": portfolio["portfolio_id"],
            "profile_url": profile_url,
            **result,
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        append_rows([row], TRADER_DETAILS_CSV_PATH, TRADER_DETAILS_CSV_HEADERS)
        total_saved += 1
        log.success(f"✓ Saved details for {row.get('name') or '(no name)'} (Total saved: {total_saved})")

        random_sleep(800, 1500)

    log.success(f"✓ Trader detail scraping complete! All details saved in: {TRADER_DETAILS_CSV_PATH}")
    return total_saved
