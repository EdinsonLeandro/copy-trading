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

TRADER_DETAILS_CSV_PATH = DATA_DIR / "trader_details.csv"
PROFILES_CSV_PATH = TRADER_DETAILS_CSV_PATH


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
