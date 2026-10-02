import csv
import random
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.common.config import (
    DEBUG_SNAPSHOTS,
    MAX_DELAY_MS,
    MIN_DELAY_MS,
    SESSION_CAP_MAX,
    SESSION_CAP_MIN,
    random_sleep,
)
from src.common.csv_store import append_rows, init_csv_file, load_existing_ids
from src.common.logger import log
from src.common.scrape_summary import TraderDetailsSummary
from src.brokers.fpmarkets.config import (
    DEBUG_DIR,
    LEADER_URLS_CSV_PATH,
    LEADER_URLS_DONE_MARKER,
    TRADER_DETAILS_CSV_PATH,
)
from src.brokers.fpmarkets.csv_schema import (
    LEADER_URLS_CSV_HEADERS,
    LEADER_URLS_ID_FIELDS,
    TRADER_DETAILS_CSV_HEADERS,
    TRADER_DETAILS_ID_FIELDS,
)
from src.brokers.fpmarkets.extractors import scrape_trader_profile
from src.brokers.fpmarkets.navigation import (
    click_next_page,
    extract_cards_from_page,
    is_next_button_disabled,
    navigate_to_leaders,
    parse_page_info,
    wait_for_leaders_page_ready,
)


def scrape_all_leader_urls(page: Page, max_pages: Optional[int] = None) -> int:
    """
    Phase 1: collects every leader's profile URL (plus card name/trader_id)
    from the Copy Trading Leaders list, paginating until the last page.

    Resumable: URLs already saved in a previous run are loaded up front and
    skipped, and each page's new URLs are appended to CSV and flushed
    immediately, so an interrupted run can be restarted without losing
    pages already covered. Reaching the true last page writes
    LEADER_URLS_DONE_MARKER so later runs skip straight to phase 2.
    """
    init_csv_file(LEADER_URLS_CSV_PATH, LEADER_URLS_CSV_HEADERS)
    seen_ids = load_existing_ids(LEADER_URLS_CSV_PATH, LEADER_URLS_ID_FIELDS)
    log.info(f"Loaded {len(seen_ids)} existing leader URLs from {LEADER_URLS_CSV_PATH.name}")

    container = navigate_to_leaders(page)

    page_idx = 1
    total_saved = 0

    while True:
        container = wait_for_leaders_page_ready(page, container)

        curr_page, total_pages = parse_page_info(container)
        display_page = curr_page if curr_page > 0 else page_idx
        display_total = total_pages if total_pages > 1 else "?"

        cards = extract_cards_from_page(container, display_page)
        log.info(f"─── Page {display_page}/{display_total}: Found {len(cards)} leaders on page ───")

        new_rows = []
        for card in cards:
            tid = card["trader_id"]
            purl = card["profile_url"]

            if (tid and tid in seen_ids) or (purl and purl in seen_ids):
                continue

            new_rows.append({
                **card,
                "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            })
            if tid:
                seen_ids.add(tid)
            if purl:
                seen_ids.add(purl)

        if new_rows:
            append_rows(new_rows, LEADER_URLS_CSV_PATH, LEADER_URLS_CSV_HEADERS)
            total_saved += len(new_rows)
            log.success(f"✓ Saved {len(new_rows)} new leader URLs (Total saved: {total_saved})")
        else:
            log.debug("No new leader URLs on this page (already scraped).")

        if max_pages and display_page >= max_pages:
            log.warning(f"Reached requested max pages limit ({max_pages}). Stopping.")
            break

        if (total_pages > 1 and display_page >= total_pages) or is_next_button_disabled(container):
            log.success("Reached the last page of the Leaders list.")
            LEADER_URLS_DONE_MARKER.write_text(
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8"
            )
            break

        log.info(f"Advancing to page {display_page + 1}...")
        click_next_page(page, container, curr_page)
        page_idx += 1

    log.success(f"✓ Leader URL collection complete! All URLs saved in: {LEADER_URLS_CSV_PATH}")
    return total_saved


def is_leader_url_collection_complete() -> bool:
    """True once scrape_all_leader_urls has reached the true last page in a
    prior run (see LEADER_URLS_DONE_MARKER) - lets a rerun skip straight to
    phase 2 instead of re-paginating the whole Leaders list."""
    return LEADER_URLS_DONE_MARKER.exists()


def reset_all_data() -> None:
    """Deletes every previous-run output (both phases' CSVs and the phase-1
    completion marker) so the pipeline restarts from a clean slate. Only
    called when RESTART_FROM_SCRATCH is set; normal runs resume instead.

    Does NOT touch debug/fpmarkets/ - see clear_debug_snapshots(), which is
    gated on DEBUG_SNAPSHOTS alone and called independently of this flag."""
    for path in (LEADER_URLS_CSV_PATH, TRADER_DETAILS_CSV_PATH, LEADER_URLS_DONE_MARKER):
        if path.exists():
            path.unlink()
            log.warning(f"RESTART_FROM_SCRATCH: deleted {path}")


def clear_debug_snapshots() -> None:
    """Deletes any screenshot/HTML dumps left in debug/fpmarkets/ from a
    prior run. Called whenever DEBUG_SNAPSHOTS is on, independent of
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


# Phase 2 anti-detection pacing (see scrape_all_trader_details): a long
# "human break" every LONG_BREAK_EVERY_MIN-LONG_BREAK_EVERY_MAX profiles, and
# a per-run cap of SESSION_CAP_MIN-SESSION_CAP_MAX profiles (set in .env,
# see src/common/config.py) so a single session doesn't hammer the site for
# the full backlog in one unbroken run.
LONG_BREAK_EVERY_MIN = 20
LONG_BREAK_EVERY_MAX = 40


def _load_leader_urls() -> list:
    if not LEADER_URLS_CSV_PATH.exists():
        return []
    with open(LEADER_URLS_CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {
                "name": row.get("name", ""),
                "trader_id": row.get("trader_id", ""),
                "profile_url": row.get("profile_url", ""),
                "page_number": row.get("page_number", ""),
            }
            for row in reader
            if row.get("profile_url")
        ]


def scrape_all_trader_details(page: Page, max_profiles: Optional[int] = None) -> TraderDetailsSummary:
    """
    Phase 2: visits every profile URL collected by scrape_all_leader_urls
    (LEADER_URLS_CSV_PATH) and scrapes its full detail-page data via
    scrape_trader_profile, saving each result to TRADER_DETAILS_CSV_PATH.

    Resumable: traders already saved in a previous run are loaded up front and
    skipped, and each profile's result is appended to CSV and flushed
    immediately, so an interrupted run can be restarted without re-scraping
    profiles already covered. One profile failing to scrape is logged and
    skipped (not saved, so it's retried next run) rather than aborting the
    whole run - except a Playwright TimeoutError, which signals FP Markets may
    be throttling/blocking the session, so that aborts the run instead.

    Anti-detection pacing: on top of the random_sleep between profiles, a
    longer "human break" is taken every LONG_BREAK_EVERY_MIN-MAX profiles,
    and - when the caller doesn't pass an explicit `max_profiles` - the run
    caps itself at a random SESSION_CAP_MIN-MAX profiles rather than
    ploughing through the whole backlog in one unbroken session.
    """
    leaders = _load_leader_urls()
    if not leaders:
        log.warning(f"No leader URLs found in {LEADER_URLS_CSV_PATH.name}. Run phase 1 first.")
        return TraderDetailsSummary(new_saved=0, total_scraped=0, remaining=0)

    init_csv_file(TRADER_DETAILS_CSV_PATH, TRADER_DETAILS_CSV_HEADERS)
    seen_ids = load_existing_ids(TRADER_DETAILS_CSV_PATH, TRADER_DETAILS_ID_FIELDS)
    log.info(f"Loaded {len(seen_ids)} existing trader details from {TRADER_DETAILS_CSV_PATH.name}")

    remaining = [
        leader for leader in leaders
        if leader["trader_id"] not in seen_ids and leader["profile_url"] not in seen_ids
    ]
    log.info(f"{len(remaining)} of {len(leaders)} profiles remain to be scraped.")
    backlog_before_run = len(remaining)

    if max_profiles is None:
        max_profiles = random.randint(SESSION_CAP_MIN, SESSION_CAP_MAX)
        log.info(f"No max_profiles given; capping this session at {max_profiles} profiles.")
    remaining = remaining[:max_profiles]

    total_saved = 0
    next_break_at = random.randint(LONG_BREAK_EVERY_MIN, LONG_BREAK_EVERY_MAX)
    for i, leader in enumerate(remaining, start=1):
        profile_url = leader["profile_url"]
        log.info(f"─── Profile {i}/{len(remaining)}: {leader['name'] or '(no name)'} (ID: {leader['trader_id']}) ───")

        try:
            profile_metrics = scrape_trader_profile(page, profile_url)
        except PlaywrightTimeoutError as e:
            log.error(
                f"Timeout while scraping profile {profile_url}: {e}. "
                "This usually means FP Markets is throttling/blocking the session - "
                "aborting the run (browser will be closed) rather than continuing."
            )
            raise
        except Exception as e:
            log.error(f"Failed to scrape profile {profile_url}: {e}")
            continue

        row = {
            **leader,
            **profile_metrics,
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        append_rows([row], TRADER_DETAILS_CSV_PATH, TRADER_DETAILS_CSV_HEADERS)
        total_saved += 1
        log.success(
            f"✓ Saved {leader['name'] or '(no name)'} | "
            f"Return(total): {profile_metrics.get('return_total') or 'N/A'} | "
            f"Age: {profile_metrics.get('age_days') or 'N/A'}d | "
            f"Month: {profile_metrics.get('return_month') or 'N/A'} "
            f"(Total saved: {total_saved})"
        )

        if i >= next_break_at:
            break_ms = random.randint(20 * MIN_DELAY_MS, 20 * MAX_DELAY_MS)
            log.info(f"Taking a longer human-like break ({break_ms / 1000:.0f}s) after {i} profiles...")
            random_sleep(break_ms, break_ms)
            next_break_at = i + random.randint(LONG_BREAK_EVERY_MIN, LONG_BREAK_EVERY_MAX)
        else:
            random_sleep(MIN_DELAY_MS, MAX_DELAY_MS)

    log.success(f"✓ Trader detail scraping complete! All details saved in: {TRADER_DETAILS_CSV_PATH}")
    remaining_after_run = backlog_before_run - total_saved
    return TraderDetailsSummary(
        new_saved=total_saved,
        total_scraped=len(leaders) - remaining_after_run,
        remaining=remaining_after_run,
    )
