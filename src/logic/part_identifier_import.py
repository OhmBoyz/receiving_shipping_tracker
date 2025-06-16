from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from src.config import DB_PATH
from src.data_manager import DataManager

REQUIRED_COLUMNS = ["part_number", "upc_code", "qty", "description"]


def _load_csv(filepath: str | Path) -> list[dict[str, str]]:
    """Load the CSV file and validate required headers."""
    path = Path(filepath)
    with path.open(newline="") as f:
        sample = f.read(2048)
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        f.seek(0)
        reader = csv.DictReader(f,dialect=dialect)
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(missing)}")
        rows = [row for row in reader]
    return rows


def _prepare_rows(rows: Iterable[dict[str, str]]) -> list[tuple[str, str, int, str]]:
    prepared = []
    for row in rows:
        part = (row.get("part_number") or "").strip()
        upc = (row.get("upc_code") or "").strip()
        qty_str = row.get("qty") or "1"
        try:
            qty = int(qty_str)
        except ValueError:
            qty = 1
        description = (row.get("description") or "").strip()
        if part:
            prepared.append((part, upc, qty, description))
    return prepared


def import_part_identifiers(filepath: str, db_path: str = DB_PATH) -> int:
    """Import ``filepath`` and return number of inserted rows."""
    raw_rows = _load_csv(filepath)
    rows = _prepare_rows(raw_rows)
    dm = DataManager(db_path)
    inserted = dm.insert_part_identifiers(rows)
    return inserted
