import random
import time
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.common.config import MAX_DELAY_MS, MIN_DELAY_MS, random_sleep
from src.common.csv_store import append_rows, init_csv_file, load_existing_ids
from src.common.logger import log
from src.brokers.fpmarkets.config import TRADER_DETAILS_CSV_PATH
from src.brokers.fpmarkets.csv_schema import CSV_HEADERS, ID_FIELDS
from src.brokers.fpmarkets.extractors import scrape_trader_profile
from src.brokers.fpmarkets.navigation import (
    extract_cards_from_page,
    get_leaders_container,
    navigate_to_leaders,
    parse_page_info,
)

# Anti-detection pacing (analog to the Binance scraper's phase 2 - see
# src/brokers/binance/orchestrator.py): a long "human break" every
# LONG_BREAK_EVERY_MIN-MAX profiles, and a per-run cap of
# SESSION_CAP_MIN-MAX newly-scraped profiles so a single session doesn't
# hammer the leaderboard across all ~105 pages in one unbroken run.
LONG_BREAK_EVERY_MIN = 20
LONG_BREAK_EVERY_MAX = 40
SESSION_CAP_MIN = 200
SESSION_CAP_MAX = 400


def scrape_all_leader_profiles(
    page: Page, max_pages: Optional[int] = None, max_profiles: Optional[int] = None
) -> int:
    """
    Two-Tab Interleaved Scraping Workflow:
    1. Tab 1 (page): Navigates to Leaders list and manages pagination across 105 pages.
    2. Tab 2 (detail_page): Navigates to each unvisited trader profile and extracts metrics.
    3. Checks existing CSV first; skips any already-scraped traders to avoid redundant requests.
    4. Appends each trader record immediately to CSV and flushes to disk.

    Anti-detection pacing: on top of the random_sleep between profiles, a longer
    "human break" is taken every LONG_BREAK_EVERY_MIN-MAX newly-scraped profiles,
    and - when the caller doesn't pass an explicit `max_profiles` - the run caps
    itself at a random SESSION_CAP_MIN-MAX profiles rather than ploughing through
    the whole leaderboard in one unbroken session. A Playwright TimeoutError
    while scraping a profile aborts the run (rather than being logged/skipped)
    since it usually signals the site is throttling/blocking the session.
    """
    if max_profiles is None:
        max_profiles = random.randint(SESSION_CAP_MIN, SESSION_CAP_MAX)
        log.info(f"No max_profiles given; capping this session at {max_profiles} profiles.")

    init_csv_file(TRADER_DETAILS_CSV_PATH, CSV_HEADERS)
    seen_ids = load_existing_ids(TRADER_DETAILS_CSV_PATH, ID_FIELDS)
    log.info(f"Loaded {len(seen_ids)} existing trader records from {TRADER_DETAILS_CSV_PATH.name}")

    # Tab 1: Initialize Leaders table & paginator
    container = navigate_to_leaders(page)

    # Tab 2: Open dedicated detail scraper tab
    log.info("Opening dedicated profile scraper tab (Tab 2)...")
    context = page.context
    detail_page = context.new_page()

    page_idx = 1
    total_saved = 0
    next_break_at = random.randint(LONG_BREAK_EVERY_MIN, LONG_BREAK_EVERY_MAX)
    session_cap_reached = False

    try:
        while True:
            # Re-acquire the Leaders container each iteration: if it lives inside an
            # iframe, that frame can be detached/replaced across a page transition,
            # which would otherwise raise on a stale `container` reference below.
            try:
                container, _ = get_leaders_container(page)
            except Exception:
                pass

            # Wait for loading indicator on Tab 1
            try:
                container.locator(".ta-loading-bar, mat-progress-bar").wait_for(state="detached", timeout=6000)
            except Exception:
                pass

            # Render pause
            random_sleep(600, 1200)

            # Parse current pagination status
            curr_page, total_pages = parse_page_info(container)
            display_page = curr_page if curr_page > 0 else page_idx
            display_total = total_pages if total_pages > 0 else (max_pages or 105)

            # Extract all trader cards on Tab 1
            page_cards = extract_cards_from_page(container, display_page)
            log.info(f"─── Page {display_page}/{display_total}: Found {len(page_cards)} traders on page ───")

            # Process each trader on the current page
            for idx, card in enumerate(page_cards, 1):
                tid = card["trader_id"]
                purl = card["profile_url"]
                name = card["name"]

                # Check if trader is already in the CSV
                if tid in seen_ids or (purl and purl in seen_ids):
                    log.debug(f"⏩ [{idx}/{len(page_cards)}] Skipping {name} (ID: {tid}) - already in CSV")
                    continue

                # Scrape profile in Tab 2
                log.info(f"🔍 [{idx}/{len(page_cards)}] Scraping profile: {name} (ID: {tid})")
                try:
                    profile_metrics = scrape_trader_profile(detail_page, purl)
                except PlaywrightTimeoutError as e:
                    log.error(
                        f"Timeout while scraping profile {purl}: {e}. "
                        "This usually means FP Markets is throttling/blocking the session - "
                        "aborting the run (browser will be closed) rather than continuing."
                    )
                    raise

                # Combine card metadata + profile metrics
                full_record = {
                    "name": name,
                    "trader_id": tid,
                    "profile_url": purl,
                    "page_number": display_page,
                    **profile_metrics,
                    "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                }

                # Save immediately to CSV
                append_rows([full_record], TRADER_DETAILS_CSV_PATH, CSV_HEADERS)
                seen_ids.add(tid)
                if purl:
                    seen_ids.add(purl)
                total_saved += 1

                log.success(
                    f"✓ Saved {name} | "
                    f"Return(total): {profile_metrics.get('return_total') or 'N/A'} | "
                    f"Age: {profile_metrics.get('age_days') or 'N/A'}d | "
                    f"Month: {profile_metrics.get('return_month') or 'N/A'} "
                    f"(Total saved: {total_saved})"
                )

                if total_saved >= max_profiles:
                    log.warning(f"Reached this session's profile cap ({max_profiles}). Stopping.")
                    session_cap_reached = True
                    break

                # Delay between profile visits - a longer human-like break every
                # LONG_BREAK_EVERY_MIN-MAX profiles, a normal one otherwise.
                if total_saved >= next_break_at:
                    break_ms = random.randint(20 * MIN_DELAY_MS, 20 * MAX_DELAY_MS)
                    log.info(f"Taking a longer human-like break ({break_ms / 1000:.0f}s) after {total_saved} profiles...")
                    random_sleep(break_ms, break_ms)
                    next_break_at = total_saved + random.randint(LONG_BREAK_EVERY_MIN, LONG_BREAK_EVERY_MAX)
                else:
                    random_sleep(MIN_DELAY_MS, MAX_DELAY_MS)

            if session_cap_reached:
                break

            # Check if max pages reached
            if max_pages and display_page >= max_pages:
                log.warning(f"Reached requested max pages limit ({max_pages}). Stopping.")
                break

            if total_pages > 1 and display_page >= total_pages:
                log.success(f"🎉 Reached final page ({total_pages}). Scraping finished!")
                break

            # Locate Next page button on Tab 1
            next_button = container.locator(
                "button.mat-paginator-navigation-next, button[aria-label='Next page'], mat-paginator button:has-text('>')",
            ).first

            if next_button.count() == 0:
                log.warning("Next page button not found. Scraping concluded.")
                break

            # Check if Next button is disabled
            is_disabled = (
                next_button.is_disabled()
                or next_button.get_attribute("disabled") is not None
                or "mat-button-disabled" in (next_button.get_attribute("class") or "")
                or next_button.get_attribute("aria-disabled") == "true"
            )

            if is_disabled:
                log.success("Next button is disabled. Reached the last page.")
                break

            # Advance Tab 1 to Next Page
            log.info(f"Advancing Tab 1 to Page {display_page + 1}...")
            try:
                next_button.scroll_into_view_if_needed()
                next_button.click(force=True)
            except Exception:
                page.evaluate("""
                    () => {
                        const next = document.querySelector("button.mat-paginator-navigation-next, button[aria-label='Next page']");
                        if (next) next.click();
                    }
                """)

            # Wait for Tab 1 page transition
            page_transitioned = False
            for _ in range(12):
                time.sleep(0.5)
                new_curr_page, _ = parse_page_info(container)
                if new_curr_page != curr_page and new_curr_page > 0:
                    page_transitioned = True
                    break

            if not page_transitioned:
                random_sleep(1500, 2500)

            page_idx += 1

    finally:
        log.debug("Closing detail scraper tab (Tab 2)...")
        try:
            detail_page.close()
        except Exception:
            pass

    log.success(f"✓ Scraping Complete! All profiles saved in: {TRADER_DETAILS_CSV_PATH}")
    return total_saved
