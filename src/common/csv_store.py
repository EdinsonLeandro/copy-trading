import csv
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set

from src.common.logger import log


def load_existing_ids(csv_path: Path, id_fields: Sequence[str]) -> Set[str]:
    """
    Loads the values of `id_fields` columns from an existing CSV, to let a
    broker's orchestrator skip records it already scraped in a prior run.

    `id_fields` is explicit (no default) since each broker's schema names its
    unique-identifier columns differently (e.g. FPMarkets: trader_id/profile_url).
    """
    seen: Set[str] = set()
    if not csv_path.exists():
        return seen

    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for field in id_fields:
                    value = row.get(field)
                    if value:
                        seen.add(value.strip())
    except Exception as e:
        log.warning(f"Warning loading existing CSV ({csv_path.name}): {e}")

    return seen


def init_csv_file(csv_path: Path, headers: Sequence[str]) -> None:
    """Initializes a CSV file with `headers` if it does not already exist."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            f.flush()


def append_rows(rows: List[Dict[str, Any]], csv_path: Path, headers: Sequence[str]) -> None:
    """Appends a batch of records to the CSV file (creating it if needed) and flushes immediately."""
    if not rows:
        return

    init_csv_file(csv_path, headers)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        for row in rows:
            writer.writerow(row)
        f.flush()
