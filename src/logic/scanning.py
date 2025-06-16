from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from src.data_manager import DataManager


def _load_csv_cache(csv_path: str) -> Dict[str, Tuple[str, int]]:
    """Load fallback UPC mappings from ``csv_path``."""
    cache: Dict[str, Tuple[str, int]] = {}
    path = Path(csv_path)
    if path.is_file():
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                part = (row.get("part_number") or "").strip().upper()
                upc = (row.get("upc_code") or "").strip().upper()
                qty_str = row.get("qty") or "1"
                try:
                    qty = int(qty_str)
                except ValueError:
                    qty = 1
                if upc:
                    cache[upc] = (part, qty)
    return cache


@dataclass
class Line:
    rowid: int
    part: str
    qty_total: int
    subinv: str
    subinv_code: str | None = None
    scanned: int = 0

    def remaining(self) -> int:
        return self.qty_total - self.scanned


class ScannerLogic:
    """Helper class implementing core scanning logic."""

    def __init__(self, dm: DataManager, csv_path: str) -> None:
        self.dm = dm
        self.csv_path = csv_path
        self._csv_cache: Dict[str, Tuple[str, int]] | None = None

    # ------------------------------------------------------------------
    def resolve_part(self, code: str) -> Tuple[str, int]:
        """Return the part number and box quantity for ``code``."""
        code = code.strip().upper()
        part, qty = self.dm.resolve_part(code)
        if part == code and qty == 1:
            if self._csv_cache is None:
                self._csv_cache = _load_csv_cache(self.csv_path)
            part, qty = self._csv_cache.get(code, (code, 1))
        return part, qty

    # ------------------------------------------------------------------
    def validate_quantity(self, qty: int, lines: List[Line]) -> None:
        """Raise ``ValueError`` if ``qty`` exceeds remaining quantity."""
        total_remaining = sum(line.remaining() for line in lines)
        if qty > total_remaining:
            raise ValueError("Quantity exceeds expected")

    # ------------------------------------------------------------------
    def allocate(self, lines: List[Line], qty: int) -> Dict[str, int]:
        """Allocate ``qty`` across ``lines`` prioritizing AMO over KANBAN."""
        self.validate_quantity(qty, lines)

        allocations = {"AMO": 0, "KANBAN": 0}
        remaining = qty
        sorted_lines = sorted(lines, key=lambda l: 0 if "AMO" in l.subinv else 1)

        for line in sorted_lines:
            if remaining == 0:
                break
            alloc = min(line.remaining(), remaining)
            if alloc:
                line.scanned += alloc
                remaining -= alloc
                if "AMO" in line.subinv:
                    allocations["AMO"] += alloc
                elif "KANBAN" in line.subinv:
                    allocations["KANBAN"] += alloc
        return allocations
