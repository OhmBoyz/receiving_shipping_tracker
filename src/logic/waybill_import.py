"""Waybill import utilities."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

DB_PATH = "receiving_tracker.db"

REQUIRED_COLUMNS = [
    "ITEM",
    "DESCRIPTION",
    "SHP QTY",
    "SUBINV",
    "Locator",
    "Waybill",
    "ITEM_COSTS",
    "SHIP_DATE",
]


def _load_excel(filepath: str | Path) -> pd.DataFrame:
    """Load the Excel waybill using pandas."""
    df = pd.read_excel(filepath, header=1)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Waybill missing columns: {', '.join(missing)}")
    return df


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned dataframe with required columns and types."""
    df = df[REQUIRED_COLUMNS].copy()
    df["ITEM"] = df["ITEM"].astype(str).str.strip()
    df["DESCRIPTION"] = df["DESCRIPTION"].astype(str).str.strip()
    df["SUBINV"] = df["SUBINV"].astype(str).str.strip()
    df["Locator"] = df["Locator"].fillna("").astype(str).str.strip()
    df["Waybill"] = df["Waybill"].astype(str).str.strip()
    df["SHP QTY"] = (
        pd.to_numeric(df["SHP QTY"], errors="coerce").fillna(0).astype(int)
    )
    df["ITEM_COSTS"] = (
        df["ITEM_COSTS"]
        .astype(str)
        .str.replace(" ", "")
        .str.replace(",", ".")
        .astype(float)
    )
    df["SHIP_DATE"] = (
        pd.to_datetime(df["SHIP_DATE"], errors="coerce").dt.date.astype(str)
    )
    return df


def _insert_rows(rows: Iterable[tuple], db_path: str) -> int:
    """Insert rows into waybill_lines and return number inserted."""
    query = (
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total,"
        " subinv, locator, description, item_cost, date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(query, rows)
        conn.commit()
        return cursor.rowcount if cursor.rowcount != -1 else len(rows)


def import_waybill(filepath: str, db_path: str = DB_PATH) -> int:
    """Import ``filepath`` and return the number of inserted rows."""
    df = _load_excel(filepath)
    df = _clean_dataframe(df)
    rows = [
        (
            row["Waybill"],
            row["ITEM"],
            row["SHP QTY"],
            row["SUBINV"],
            row["Locator"],
            row["DESCRIPTION"],
            row["ITEM_COSTS"],
            row["SHIP_DATE"],
        )
        for _, row in df.iterrows()
    ]
    inserted = _insert_rows(rows, db_path)
    return inserted
