import os

from src.common.config import (
    AUTH_STATE_DIR as _AUTH_STATE_DIR,
    DATA_DIR as _DATA_DIR,
    DEBUG_DIR as _DEBUG_DIR,
    ensure_directories as _ensure_directories,
)

BROKER_NAME = "binance"

# Credentials
BINANCE_EMAIL = os.getenv("BINANCE_EMAIL", "").strip()
BINANCE_PASSWORD = os.getenv("BINANCE_PASSWORD", "").strip()

# Target URLs
LOGIN_URL = "https://accounts.binance.com/en/login"
HOME_URL = LOGIN_URL
PORTFOLIO_BASE_URL = "https://www.binance.com"
COPY_TRADING_URL = "https://www.binance.com/en/copy-trading"

# How long to pause after submitting the password so the account owner can
# approve the "Security Verification" app-push prompt on their phone.
SECURITY_VERIFICATION_WAIT_SECONDS = 30

# How long to pause after submitting the email so a manual captcha (Binance
# sometimes shows one at this step) can be solved before typing the password.
EMAIL_SUBMIT_WAIT_SECONDS = 30

# Paths (namespaced under the shared common/ directories by broker name)
DATA_DIR = _DATA_DIR / BROKER_NAME
DEBUG_DIR = _DEBUG_DIR / BROKER_NAME
AUTH_STATE_PATH = _AUTH_STATE_DIR / f"{BROKER_NAME}.json"

TRADER_DETAILS_CSV_PATH = DATA_DIR / "trader_details.csv"

# Phase 1 output: just the portfolio (trader) profile URLs discovered while
# paginating the leaderboard. Kept separate from TRADER_DETAILS_CSV_PATH since
# that file is for the (future) per-profile detail scrape, a distinct resumable
# phase that reads this file as its input list.
PORTFOLIO_URLS_CSV_PATH = DATA_DIR / "portfolio_urls.csv"


def ensure_directories() -> None:
    """Creates this broker's output directories. Called explicitly at startup
    rather than as an import side effect, so importing config stays safe in tests."""
    _ensure_directories(DATA_DIR, DEBUG_DIR, AUTH_STATE_PATH.parent)


def validate_credentials() -> None:
    """Ensures credentials are provided before attempting login."""
    if not BINANCE_EMAIL or not BINANCE_PASSWORD:
        raise ValueError(
            "Missing credentials in .env file! Please set BINANCE_EMAIL and BINANCE_PASSWORD."
        )
