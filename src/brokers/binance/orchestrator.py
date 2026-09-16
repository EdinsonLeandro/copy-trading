from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import Page

from src.common.config import random_sleep
from src.common.csv_store import append_rows, init_csv_file, load_existing_ids
from src.common.logger import log
from src.brokers.binance.config import PORTFOLIO_URLS_CSV_PATH
from src.brokers.binance.csv_schema import PORTFOLIO_URLS_CSV_HEADERS, PORTFOLIO_URLS_ID_FIELDS
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
            break

        log.info(f"Advancing to page {display_page + 1}...")
        click_next_page(page)
        random_sleep(600, 1200)
        page_idx += 1

    log.success(f"✓ Portfolio URL collection complete! All URLs saved in: {PORTFOLIO_URLS_CSV_PATH}")
    return total_saved
