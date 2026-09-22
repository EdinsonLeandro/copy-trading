# Copy Trading Leaderboard Scraper

An automated, multi-broker web scraper for copy-trading leaderboards, built with **Python 3.11** and **Playwright**.

> [!IMPORTANT]
> **What this project is (and isn't):** despite the repo name "copy-trading", this tool does **not** place trades, manage positions, or execute copy-trading on your behalf. It automates a browser to log into each broker's portal and **scrape publicly-visible statistics about copy-trading "leaders"** (traders other users can choose to copy) — returns, drawdown, leverage, instruments traded, etc. — into local CSV files for offline analysis. There is no order execution, no broker trading API integration, and no capital at risk from running it.

---

## 📁 Project Structure

The codebase is split into a broker-agnostic **common** layer and one **broker package per platform**, since each broker has its own website, its own login/2FA flow, and its own trader-data schema — only the underlying browser-automation plumbing is shared.

```text
copy-trading/
├── .env.example            # Environment variables template
├── .env                     # Your secret credentials (gitignored)
├── .gitignore
├── requirements.txt
├── pytest.ini
├── main.py                  # Entry point: python main.py --broker <name>
├── README.md
├── logs/                    # Auto-captured run logs (per broker, via log.set_label)
├── debug/<broker>/          # Auto-captured screenshots + HTML dumps on login/extraction errors, per broker
├── data/<broker>/           # Extracted CSV datasets, per broker
├── auth_state/<broker>.json # Saved login session per broker (gitignored)
├── scripts/
│   └── test_binance_profile_extractor.py  # Dev-only sanity check for binance/extractors.py
├── tests/
│   ├── common/              # Tests for the shared infrastructure
│   └── fpmarkets/           # Tests for the FP Markets scraper
└── src/
    ├── common/               # Broker-agnostic infrastructure
    │   ├── config.py          # BASE_DIR, HEADLESS, DEBUG_SNAPSHOTS, delay settings, ensure_directories
    │   ├── logger.py          # Leveled console + file logger (info/success/warning/error/debug)
    │   ├── browser_session.py # Playwright launch, anti-detection args, storage-state reuse, human_type
    │   ├── playwright_utils.py# Frame-fallback JS eval, poll-until-populated, generic tab clicking
    │   └── csv_store.py       # Generic CSV init/append/dedup, parameterized by each broker's own schema
    │
    └── brokers/
        ├── fpmarkets/         # FP Markets: reference implementation
        │   ├── config.py       # Credentials, URLs, per-broker paths, validate_credentials()
        │   ├── auth.py         # FP Markets login flow (built on common/browser_session.py)
        │   ├── csv_schema.py   # This broker's CSV_HEADERS + ID_FIELDS (dedup key columns)
        │   ├── navigation.py   # Leaders list navigation, pagination, card extraction
        │   ├── extractors.py   # Per-tab JS extraction scripts + profile scraping
        │   ├── orchestrator.py # Top-level scrape_all_leader_profiles() loop
        │   └── run.py          # Wires auth + orchestrator together for main.py
        │
        └── binance/            # Binance: both phases implemented and wired into main.py
            ├── config.py        # Credentials, URLs, per-broker paths, validate_credentials()
            ├── auth.py          # Binance login flow (handles email/password + manual captcha/app-push waits)
            ├── csv_schema.py    # PORTFOLIO_URLS_CSV_HEADERS/TRADER_DETAILS_CSV_HEADERS + ID fields
            ├── navigation.py    # Copy Trading tab navigation, pagination, portfolio card extraction
            ├── extractors.py    # Per-tab JS extraction scripts + profile scraping
            ├── orchestrator.py  # scrape_all_portfolio_urls() (Phase 1) + scrape_all_trader_details() (Phase 2),
            │                    # plus resumability helpers (completion marker, reset-from-scratch, debug cleanup)
            └── run.py           # Wires auth + both phases together for main.py
```

Adding a new broker (e.g. OKX) means adding a new `src/brokers/<name>/` package with the same shape as `fpmarkets/` or `binance/`, and registering its `run()` in `main.py`'s `BROKER_RUNNERS` dict. Nothing in `src/common/` should ever need to know a specific broker's name, URLs, or data fields — if it does, that logic belongs in the broker package instead.

---

## 🚀 Getting Started

### 1. Create and Activate Virtual Environment (`.venv`)

Open your terminal in the project root directory and run:

**On Windows (PowerShell):**
```powershell
# Create the virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

*(If you encounter an execution policy error in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

**On Windows (Command Prompt / CMD):**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 2. Install Dependencies & Playwright Browsers

Install the Python libraries:
```bash
pip install -r requirements.txt
```

Install the Playwright browser binaries (Chromium):
```bash
playwright install chromium
```

---

### 3. Configure Credentials

1. Copy `.env.example` to `.env` in the root directory.
2. Fill in the login credentials for whichever broker(s) you'll run (each broker gets its own section in `.env`):

```env
# --- Broker-agnostic settings ---
HEADLESS=False
MIN_DELAY_MS=300
MAX_DELAY_MS=800
DEBUG_SNAPSHOTS=False
RESTART_FROM_SCRATCH=False

# --- FP Markets credentials ---
FPMARKETS_EMAIL=your_actual_email@example.com
FPMARKETS_PASSWORD=your_actual_password
FPMARKETS_PIN=your_account_pin

# --- Binance credentials ---
BINANCE_EMAIL=your_actual_email@example.com
BINANCE_PASSWORD=your_actual_password
```

> [!NOTE]
> Binance's login flow may pause for a manual captcha after submitting the email, and again for an app-push "Security Verification" prompt after the password — approve these on your device/browser when they appear; the script waits before continuing.

> [!NOTE]
> `HEADLESS=False` ensures you can visually watch the browser navigate, fill the fields, and handle any 2FA/PIN prompts if requested by the portal.

> [!WARNING]
> `.env` and the generated `auth_state/<broker>.json` files (saved login sessions/cookies) contain real credentials/session data in plaintext. Both are gitignored, but keep them out of any screenshots, logs, or shared copies of this folder.

---

### 4. Run a Scraper

```bash
python main.py --broker fpmarkets
python main.py --broker binance
```

Use `--force-fresh-login` to ignore any saved session and log in again.

FP Markets scrapes full leader profiles end-to-end. Binance runs both phases in sequence within a single browser session: Phase 1 paginates the Copy Trading leaderboard and saves every trader's profile URL to `data/binance/portfolio_urls.csv`, then Phase 2 visits each of those URLs and scrapes its full detail-page data into `data/binance/trader_details.csv`. Both phases are resumable — see `scripts/test_binance_profile_extractor.py` for a standalone sanity check of the Phase 2 extractor against real profile URLs, outside the full pipeline.

> [!NOTE]
> Binance does not allow multiple simultaneous sessions on one account login, so Phase 2 cannot be parallelized across multiple browser instances - both phases run sequentially in a single session.

### Key Features
* **Session Persistence (`auth_state/<broker>.json`)**: Once logged in successfully, your session cookies and storage state are saved per broker. Subsequent runs bypass the login page and load the dashboard directly.
* **Resumable, Interruption-Safe Scraping**: Every profile/URL is written to its CSV immediately after being scraped, not batched at the end - killing the process (or losing your connection) mid-run and restarting picks up exactly where it left off, with no duplicate rows. For Binance specifically, once Phase 1 reaches the true last page it writes a completion marker (`data/binance/portfolio_urls.done`) so a rerun skips straight to Phase 2 instead of re-paginating the ~600-page leaderboard just to confirm nothing changed. Set `RESTART_FROM_SCRATCH=True` in `.env` to instead wipe a broker's saved CSVs/marker and start completely over.
* **Error & 2FA Detection**: Automatically captures error messages and screenshots into `debug/<broker>/` if authentication fails, if a PIN is requested, or if an extraction comes back incomplete (when `DEBUG_SNAPSHOTS=True`). Snapshots left over from a previous run are cleared automatically at the start of the next one.
* **Anti-Bot Friendly**: Runs with standard user agents and browser flags to prevent automated bot detection.

---

## 🧪 Running Tests

Unit tests cover the pure-logic pieces (generic CSV persistence, pagination-label parsing, leverage-chart date reconstruction) that don't require a live browser:

```bash
pytest
```

Browser-driven scraping/login logic is not covered by automated tests — verify those manually by running `python main.py --broker <name>` against the live portal.

---

## 📝 Logs

Every run writes a leveled log (`INFO` / `SUCCESS` / `WARNING` / `ERROR` / `DEBUG`) to both the console (color-coded via `rich`) and to `logs/run_<broker>_<timestamp>.log` / `logs/latest_<broker>.log`.
