# FP Markets Web Scraper & Data Analysis

An automated, robust web scraper and data extractor for the FP Markets Portal built with **Python 3.11** and **Playwright**.

> [!IMPORTANT]
> **What this project is (and isn't):** despite the repo name "copy-trading", this tool does **not** place trades, manage positions, or execute copy-trading on your behalf. It automates a browser to log into the FP Markets portal and **scrape publicly-visible statistics about copy-trading "leaders"** (traders other users can choose to copy) — returns, drawdown, leverage, instruments traded, etc. — into a local CSV file for offline analysis. There is no order execution, no broker trading API integration, and no capital at risk from running it.

---

## 📁 Project Structure

```text
copy-trading/
├── .env.example          # Environment variables template
├── .env                  # Your secret credentials (gitignored)
├── .gitignore             # Git exclusion rules
├── requirements.txt       # Python dependencies
├── pytest.ini             # Pytest configuration
├── main.py                # Application entry point
├── README.md               # Project documentation
├── logs/                    # Auto-captured run logs (e.g. run_YYYYMMDD_HHMMSS.log, latest.log)
├── screenshots/             # Auto-captured screenshots on login/errors
├── data/                    # Extracted CSV datasets (e.g. trader_details.csv)
├── tests/                   # Unit tests for the pure-logic pieces (pytest)
│   ├── test_csv_store.py
│   ├── test_extractors.py
│   └── test_navigation.py
└── src/
    ├── __init__.py
    ├── config.py            # Settings, env variable loader, path constants
    ├── logger.py            # Leveled console + file logger (info/success/warning/error/debug)
    ├── auth.py              # Playwright login, PIN handler, and session persistence
    └── scraper/             # Copy Trading leaderboard scraper, split by responsibility
        ├── __init__.py       # Public API re-exports
        ├── csv_store.py      # CSV schema + read/write/dedup persistence
        ├── dom_utils.py      # Shared DOM helpers: frame-fallback JS eval, tab clicking
        ├── navigation.py     # Leaders list navigation, pagination, card extraction
        ├── extractors.py     # Per-tab JS extraction scripts + profile scraping
        └── orchestrator.py   # Top-level scrape_all_leader_profiles() loop
```

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

1. Open the [`.env`](file:///.env) file in the root directory.
2. Fill in your FP Markets login credentials:

```env
# FP Markets Credentials
FPMARKETS_EMAIL=your_actual_email@example.com
FPMARKETS_PASSWORD=your_actual_password
FPMARKETS_PIN=your_account_pin

# Playwright & Anti-Detection Settings
HEADLESS=False
MIN_DELAY_MS=300
MAX_DELAY_MS=800
```

> [!NOTE]
> `HEADLESS=False` ensures you can visually watch the browser navigate, fill the fields, and handle any 2FA/PIN prompts if requested by the portal.

> [!WARNING]
> `.env` and the generated `auth_state.json` (saved login session/cookies) contain real credentials/session data in plaintext. Both are gitignored, but keep them out of any screenshots, logs, or shared copies of this folder.

---

### 4. Run the Login & Scraper

Execute the main script:
```bash
python main.py
```

### Key Features
* **Session Persistence (`auth_state.json`)**: Once logged in successfully, your session cookies and storage state are saved. Subsequent runs will bypass the login page and load the dashboard directly!
* **Error & 2FA Detection**: Automatically captures error messages and screenshots into `screenshots/` if authentication fails or if a PIN is requested.
* **Anti-Bot Friendly**: Runs with standard user agents and browser flags to prevent automated bot detection.

---

## 🧪 Running Tests

Unit tests cover the pure-logic pieces (CSV persistence, pagination-label parsing, leverage-chart date reconstruction) that don't require a live browser:

```bash
pytest
```

Browser-driven scraping/login logic is not covered by automated tests — verify those manually by running `python main.py` against the live portal.

---

## 📝 Logs

Every run writes a leveled log (`INFO` / `SUCCESS` / `WARNING` / `ERROR` / `DEBUG`) to both the console (color-coded via `rich`) and to `logs/run_<timestamp>.log` / `logs/latest.log`.
