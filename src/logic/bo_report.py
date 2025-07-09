from __future__ import annotations

import math
import pandas as pd
from pathlib import Path
from typing import Dict, Set, Tuple, List
from datetime import datetime

from src.config import DB_PATH
from src.data_manager import DataManager

# Helper function to find a column by keyword, case-insensitive
def _find_column(columns: list[str], keyword: str) -> str:
    """Finds a column in a list of columns by keyword (case-insensitive)."""
    keyword = keyword.lower()
    for col in columns:
        if keyword in col.lower():
            return col
    raise KeyError(f"Column containing '{keyword}' not found in {list(columns)}")

def _clean_str(v) -> str:
    """Converts value to a clean string, handling None, NaN, and floats."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()

def read_backlog_df(file_path: str | Path) -> pd.DataFrame:
    """Reads and processes the BACKLOG Excel file."""
    try:
        df = pd.read_excel(file_path, sheet_name='Sheet1')
        c_go = _find_column(df.columns, "GO")
        c_it = _find_column(df.columns, "Item")
        c_pr = _find_column(df.columns, "Product ID")
        c_qty = _find_column(df.columns, "Qty")
        c_shop = _find_column(df.columns, "Shop Order")
        c_orabl = _find_column(df.columns, "oracleordernum")

        # Filter for valid item formats (e.g., 123W, 45S)
        mask = df[c_it].astype(str).str.match(r"^\d{2,3}[SW]\d?$", na=False)
        bl = df[mask].copy()

        bl["go_item"] = bl[c_go].astype(str) + "-" + bl[c_it].astype(str)
        bl["item_number"] = bl[c_it].apply(_clean_str)
        bl["part_number"] = bl[c_pr].astype(str).str.rstrip(".")
        bl["qty_req"] = bl[c_qty].fillna(0).astype(int)
        bl["discrete_job"] = bl[c_shop].apply(_clean_str)
        bl["oracle_bl"] = bl[c_orabl].apply(_clean_str)

        return bl.set_index(["go_item", "part_number"])
    except Exception as e:
        raise ValueError(f"Error reading BACKLOG file: {e}") from e

def read_redcon_df(file_path: str | Path) -> pd.DataFrame:
    """Reads and processes the REDCON Excel file."""
    try:
        df = pd.read_excel(file_path, sheet_name='Export')
        cg = _find_column(df.columns, "GO ITEM")
        cp = _find_column(df.columns, "PART NUMBER")
        cf = _find_column(df.columns, "FLOW STATUS")
        co = _find_column(df.columns, "ORACLE NUMBER")

        rc_norm = pd.DataFrame({
            "go_item": df[cg].astype(str),
            "part_number": df[cp].astype(str).str.rstrip("."),
            "flow_status": df[cf].fillna("AWAITING_SHIPPING").astype(str),
            "oracle_rc": df[co].apply(_clean_str),
        })

        return (
            rc_norm.sort_values(["go_item", "part_number"])
                   .groupby(["go_item", "part_number"], as_index=False)
                   .last()
                   .set_index(["go_item", "part_number"])
        )
    except Exception as e:
        raise ValueError(f"Error reading REDCON file: {e}") from e

def sync_bo_data(backlog_df: pd.DataFrame, redcon_df: pd.DataFrame) -> List[Dict[str, any]]:
    """
    Merges the backlog and redcon dataframes, keeping only common items.
    Returns a list of dictionaries ready for database insertion.
    """
    keys_common: Set[Tuple[str, str]] = set(backlog_df.index) & set(redcon_df.index)
    
    records_to_insert = []
    
    for key in keys_common:
        go_item, part_number = key
        bl_row = backlog_df.loc[key]
        rc_row = redcon_df.loc[key]

        oracle = _clean_str(bl_row["oracle_bl"]) or _clean_str(rc_row["oracle_rc"])

        payload = {
            "go_item": go_item,
            "oracle": oracle,
            "item_number": _clean_str(bl_row["item_number"]),
            "discrete_job": _clean_str(bl_row["discrete_job"]),
            "part_number": part_number,
            "qty_req": int(bl_row["qty_req"]),
            "flow_status": _clean_str(rc_row["flow_status"]) or "AWAITING_SHIPPING",
            "last_import_date": datetime.now().date().isoformat(),
        }
        records_to_insert.append(payload)
        
    return records_to_insert

def import_bo_files(backlog_path: str, redcon_path: str, db_path: str = DB_PATH) -> Tuple[int, int]:
    """
    Orchestrates the import process for BO files and returns counts.
    """
    backlog_df = read_backlog_df(backlog_path)
    redcon_df = read_redcon_df(redcon_path)
    
    records = sync_bo_data(backlog_df, redcon_df)
    
    dm = DataManager(db_path)
    created, updated = dm.insert_bo_items(records)
    
    return created, updated