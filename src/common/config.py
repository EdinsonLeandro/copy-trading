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

# Which installed browser to drive. "chrome" (the default) uses the real
# Google Chrome install, whose Client Hints carry the "Google Chrome" brand
# like any normal visitor; empty falls back to the bundled Chromium build.
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome").strip()

# When True, a broker's run() wipes its previously saved output (URL/detail
# CSVs, the phase-1 completion marker, and any debug snapshots) before
# starting, so the whole pipeline restarts from a clean slate instead of
# resuming. Off by default since resuming is the normal/expected behavior.
RESTART_FROM_SCRATCH = os.getenv("RESTART_FROM_SCRATCH", "False").lower() in ("true", "1", "yes")

# Per-run cap on newly-scraped profiles, shared by every broker: each run
# picks a random number in [SESSION_CAP_MIN, SESSION_CAP_MAX] and stops once
# it has saved that many, so no single session ploughs through the whole
# backlog in one unbroken run (an anti-detection measure).
SESSION_CAP_MIN = int(os.getenv("SESSION_CAP_MIN", "100"))
SESSION_CAP_MAX = int(os.getenv("SESSION_CAP_MAX", "130"))


def get_random_delay_ms(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS) -> int:
    """Returns a random delay in milliseconds between min and max."""
    return random.randint(min(min_ms, max_ms), max(min_ms, max_ms))


def random_sleep(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS):
    """Sleeps for a random duration between min and max milliseconds."""
    delay_sec = get_random_delay_ms(min_ms, max_ms) / 1000.0
    time.sleep(delay_sec)


# Long-tailed pause tiers: (cumulative probability, low, high) with the
# bounds as multiples of max_ms. A uniform min-max delay produces an
# unnaturally regular rhythm; a real visitor mostly moves on quickly but
# sometimes lingers on a page or gets distracted for a while. With the
# default 300-800 ms that is: 70% 0.3-0.8 s, 23% 2.4-8 s, 7% 12-36 s.
_LONG_TAIL_MEDIUM_ROLL = 0.70
_LONG_TAIL_LONG_ROLL = 0.93
_LONG_TAIL_MEDIUM_RANGE = (3, 10)
_LONG_TAIL_LONG_RANGE = (15, 45)


def get_long_tail_delay_ms(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS, rng=random) -> int:
    """Returns a random delay that is usually short (min_ms-max_ms) but
    occasionally several times longer (see the tiers above). Which tier is
    used is picked at random on every call."""
    low, high = min(min_ms, max_ms), max(min_ms, max_ms)
    roll = rng.random()
    if roll < _LONG_TAIL_MEDIUM_ROLL:
        return rng.randint(low, high)
    if roll < _LONG_TAIL_LONG_ROLL:
        return rng.randint(_LONG_TAIL_MEDIUM_RANGE[0] * high, _LONG_TAIL_MEDIUM_RANGE[1] * high)
    return rng.randint(_LONG_TAIL_LONG_RANGE[0] * high, _LONG_TAIL_LONG_RANGE[1] * high)


def long_tail_sleep(min_ms: int = MIN_DELAY_MS, max_ms: int = MAX_DELAY_MS) -> None:
    """Sleeps for get_long_tail_delay_ms(min_ms, max_ms) milliseconds."""
    time.sleep(get_long_tail_delay_ms(min_ms, max_ms) / 1000.0)


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
