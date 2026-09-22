import os
import random
import time
from pathlib import Path
from dotenv import load_dotenv

# Repo root (this file lives at src/common/config.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

# Broker-agnostic browser & anti-detection configurations
HEADLESS = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")
DEBUG_SNAPSHOTS = os.getenv("DEBUG_SNAPSHOTS", "False").lower() in ("true", "1", "yes")
MIN_DELAY_MS = int(os.getenv("MIN_DELAY_MS", "300"))
MAX_DELAY_MS = int(os.getenv("MAX_DELAY_MS", "800"))

# When True, a broker's run() wipes its previously saved output (URL/detail
# CSVs, the phase-1 completion marker, and any debug snapshots) before
# starting, so the whole pipeline restarts from a clean slate instead of
# resuming. Off by default since resuming is the normal/expected behavior.
RESTART_FROM_SCRATCH = os.getenv("RESTART_FROM_SCRATCH", "False").lower() in ("true", "1", "yes")


def get_random_delay_ms(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS) -> int:
    """Returns a random delay in milliseconds between min and max."""
    return random.randint(min(min_ms, max_ms), max(min_ms, max_ms))


def random_sleep(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS):
    """Sleeps for a random duration between min and max milliseconds."""
    delay_sec = get_random_delay_ms(min_ms, max_ms) / 1000.0
    time.sleep(delay_sec)


# Root output directories. Each broker keeps its own subfolder under these
# (e.g. DATA_DIR / "fpmarkets") since trader data schemas differ per platform.
DATA_DIR = BASE_DIR / "data"
# Login-failure and extraction-failure snapshots (screenshot + full HTML),
# not feature output - named for what's actually in there.
DEBUG_DIR = BASE_DIR / "debug"
AUTH_STATE_DIR = BASE_DIR / "auth_state"


def ensure_directories(*dirs: Path) -> None:
    """Creates the given directories (and parents) if missing. Called explicitly
    at startup rather than as an import side effect, so importing config stays
    safe in tests."""
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
