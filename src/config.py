import os
import random
import time
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

# Credentials
FPMARKETS_EMAIL = os.getenv("FPMARKETS_EMAIL", "").strip()
FPMARKETS_PASSWORD = os.getenv("FPMARKETS_PASSWORD", "").strip()
FPMARKETS_PIN = os.getenv("FPMARKETS_PIN", "").strip()

# Browser & anti-detection configurations
HEADLESS = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")
MIN_DELAY_MS = int(os.getenv("MIN_DELAY_MS", "300"))
MAX_DELAY_MS = int(os.getenv("MAX_DELAY_MS", "800"))


def get_random_delay_ms(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS) -> int:
    """Returns a random delay in milliseconds between min and max."""
    return random.randint(min(min_ms, max_ms), max(min_ms, max_ms))


def random_sleep(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS):
    """Sleeps for a random duration between min and max milliseconds."""
    delay_sec = get_random_delay_ms(min_ms, max_ms) / 1000.0
    time.sleep(delay_sec)

# Target URLs
LOGIN_URL = "https://portal.fpmarkets.com/login"
COPY_TRADING_URL = "https://portal.fpmarkets.com/sc-EN/copy-trading"
SOCIAL_RATINGS_BASE_URL = "https://socialratings.fpglobaltrading.com"

# Paths
AUTH_STATE_PATH = BASE_DIR / "auth_state.json"
DATA_DIR = BASE_DIR / "data"
TRADER_DETAILS_CSV_PATH = DATA_DIR / "trader_details.csv"
PROFILES_CSV_PATH = TRADER_DETAILS_CSV_PATH
SCREENSHOTS_DIR = BASE_DIR / "screenshots"


def ensure_directories():
    """Creates runtime output directories. Called explicitly at startup rather
    than as an import side effect, so importing this module stays safe in tests."""
    DATA_DIR.mkdir(exist_ok=True)
    SCREENSHOTS_DIR.mkdir(exist_ok=True)


def validate_credentials():
    """Ensures credentials are provided before attempting login."""
    if not FPMARKETS_EMAIL or not FPMARKETS_PASSWORD:
        raise ValueError(
            "Missing credentials in .env file! Please set FPMARKETS_EMAIL and FPMARKETS_PASSWORD."
        )

