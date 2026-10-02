import os

from src.common.config import (
    AUTH_STATE_DIR as _AUTH_STATE_DIR,
    DATA_DIR as _DATA_DIR,
    DEBUG_DIR as _DEBUG_DIR,
    ensure_directories as _ensure_directories,
)

BROKER_NAME = "fpmarkets"

# Credentials
FPMARKETS_EMAIL = os.getenv("FPMARKETS_EMAIL", "").strip()
FPMARKETS_PASSWORD = os.getenv("FPMARKETS_PASSWORD", "").strip()
FPMARKETS_PIN = os.getenv("FPMARKETS_PIN", "").strip()

# Target URLs
LOGIN_URL = "https://portal.fpmarkets.com/login"
HOME_URL = "https://portal.fpmarkets.com/"
COPY_TRADING_URL = "https://portal.fpmarkets.com/sc-EN/copy-trading"
SOCIAL_RATINGS_BASE_URL = "https://socialratings.fpglobaltrading.com"

# Paths (namespaced under the shared common/ directories by broker name)
DATA_DIR = _DATA_DIR / BROKER_NAME
DEBUG_DIR = _DEBUG_DIR / BROKER_NAME
AUTH_STATE_PATH = _AUTH_STATE_DIR / f"{BROKER_NAME}.json"
# Persistent Chrome profile (cookies, IndexedDB, cache, history) reused on
# every run so the site sees the same returning device. Holds session
# cookies, so it lives under the gitignored auth_state/ like AUTH_STATE_PATH.
BROWSER_PROFILE_DIR = _AUTH_STATE_DIR / f"{BROKER_NAME}_profile"

TRADER_DETAILS_CSV_PATH = DATA_DIR / "trader_details.csv"

# Phase 1 output: the leader (trader) profile URLs discovered while
# paginating the Leaders list, plus the card name (the profile page itself
# doesn't carry it). Kept separate from TRADER_DETAILS_CSV_PATH since that
# file is for the per-profile detail scrape (phase 2), a distinct resumable
# phase that reads this file as its input list.
LEADER_URLS_CSV_PATH = DATA_DIR / "leader_urls.csv"

# Written once scrape_all_leader_urls reaches the true last page (Next
# button disabled), not just an early/max_pages stop. Its presence lets a
# rerun skip straight to phase 2 instead of re-paginating the entire
# Leaders list just to confirm there's nothing new to add.
LEADER_URLS_DONE_MARKER = DATA_DIR / "leader_urls.done"


def ensure_directories() -> None:
    """Creates this broker's output directories. Called explicitly at startup
    rather than as an import side effect, so importing config stays safe in tests."""
    _ensure_directories(DATA_DIR, DEBUG_DIR, AUTH_STATE_PATH.parent)


def validate_credentials() -> None:
    """Ensures credentials are provided before attempting login."""
    if not FPMARKETS_EMAIL or not FPMARKETS_PASSWORD:
        raise ValueError(
            "Missing credentials in .env file! Please set FPMARKETS_EMAIL and FPMARKETS_PASSWORD."
        )
