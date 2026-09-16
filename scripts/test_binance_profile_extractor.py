"""
Standalone sanity check for src/brokers/binance/extractors.py.

Reuses the already-saved Binance session (auth_state/binance.json) and runs
scrape_trader_profile() against one or more real profile URLs, saving the
extracted fields to a CSV (scripts/binance_profile_extractor_test_results.csv)
so they can be compared against what's rendered in the browser before wiring
the extractor into a full orchestrator/worker pool.

This is a dev-only sanity script, not part of the resumable production
pipeline: each run overwrites the output CSV from scratch rather than
appending/de-duping across runs.

Usage:
    python scripts/test_binance_profile_extractor.py <profile_url> [<profile_url> ...]

    # or, to pull a batch of URLs straight from portfolio_urls.csv:
    python scripts/test_binance_profile_extractor.py
"""
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.brokers.binance.auth import get_authenticated_session
from src.brokers.binance.config import PORTFOLIO_URLS_CSV_PATH
from src.brokers.binance.csv_schema import TRADER_DETAILS_CSV_HEADERS
from src.brokers.binance.extractors import scrape_trader_profile
from src.common.logger import log

DEFAULT_SAMPLE_SIZE = 30
OUTPUT_CSV_PATH = Path(__file__).resolve().parent / "binance_profile_extractor_test_results.csv"


def _sample_urls_from_csv(limit: int) -> list:
    if not PORTFOLIO_URLS_CSV_PATH.exists():
        return []
    with open(PORTFOLIO_URLS_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row["profile_url"] for row in reader if row.get("profile_url")][:limit]


def main() -> None:
    urls = sys.argv[1:] or _sample_urls_from_csv(DEFAULT_SAMPLE_SIZE)
    if not urls:
        log.error(
            f"No profile URLs given and none found in {PORTFOLIO_URLS_CSV_PATH}. "
            "Pass one or more profile URLs as arguments."
        )
        raise SystemExit(1)

    log.info(f"Testing extractor against {len(urls)} profile(s)...")
    playwright, browser, context, page = get_authenticated_session(force_fresh_login=False)

    if not page:
        log.error("Failed to open an authenticated Binance session.")
        raise SystemExit(1)

    rows = []
    try:
        for url in urls:
            log.info(f"--- {url} ---")
            result = scrape_trader_profile(page, url)

            id_match = re.search(r"lead-details/(\d+)", url)
            row = {
                "portfolio_id": id_match.group(1) if id_match else "",
                "profile_url": url,
                **result,
                "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            rows.append(row)
            log.success(f"✓ Extracted {row.get('name') or '(no name)'}")
    finally:
        context.close()
        browser.close()
        playwright.stop()

    with open(OUTPUT_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRADER_DETAILS_CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    log.success(f"✓ Saved {len(rows)} profile(s) to {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()
