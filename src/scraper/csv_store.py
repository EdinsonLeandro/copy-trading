import csv
from pathlib import Path
from typing import List, Dict, Set, Any

from src.config import TRADER_DETAILS_CSV_PATH
from src.logger import log

CSV_HEADERS = [
    "name",
    "trader_id",
    "profile_url",
    "page_number",
    # Top Summary Header
    "return_total",
    "return_1d",
    "age_days",
    # Return/period Section
    "return_all_time",
    "return_year",
    "return_half_year",
    "return_quarter",
    "return_month",
    "return_week",
    "return_day",
    # Monthly Section
    "avg_return_weekly",
    "avg_return_monthly",
    "return_deviation",
    "return_deviation_monthly",
    "return_deviation_yearly",
    # Monthly bar chart (JSON object: {"Jan'26": "-34.87", ...})
    "monthly_chart",
    # Trading tab
    "trading_return_volatility_d",
    "trading_recovery_factor",
    "trading_absolute_gain",
    "trading_downside_deviation",
    "trading_sharpe_ratio",
    "trading_volatility_ratio",
    "trading_max_profit",
    "trading_max_drawdown",
    # Leverage bar chart (JSON array: [{"value": "0", "date": "2026-02-01"}, ...])
    "leverage_chart",
    # Instruments tab
    # Donut legend, trade count per symbol (JSON object: {"BTCUSD": "24", ...})
    "instruments",
    # Trade Statistics list (JSON object: {"Best trade": "$94.19", ...})
    "trade_statistics",
    # Metadata
    "scraped_at",
]


def load_existing_trader_ids(csv_path: Path = TRADER_DETAILS_CSV_PATH) -> Set[str]:
    """Loads already scraped trader IDs / URLs to avoid duplicates across runs."""
    seen: Set[str] = set()
    if not csv_path.exists():
        return seen

    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = row.get("trader_id")
                purl = row.get("profile_url")
                if tid:
                    seen.add(tid.strip())
                if purl:
                    seen.add(purl.strip())
    except Exception as e:
        log.warning(f"Warning loading existing CSV: {e}")

    return seen


def init_csv_file(csv_path: Path = TRADER_DETAILS_CSV_PATH):
    """Initializes CSV file with headers if it does not exist."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
            f.flush()


def append_profiles_to_csv(profiles: List[Dict[str, Any]], csv_path: Path = TRADER_DETAILS_CSV_PATH):
    """Appends a batch of scraped trader profiles to the CSV file and flushes immediately."""
    if not profiles:
        return

    init_csv_file(csv_path)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        for profile in profiles:
            writer.writerow(profile)
        f.flush()
