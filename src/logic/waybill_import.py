"""
Module: waybill_import.py

Handles importing a Waybill Excel file and inserting valid entries into the database.

Expected format: See section 7 of docs/spec.md
"""

import sqlite3
import pandas as pd

def import_waybill(filepath: str, db_path: str):
    # TODO: Load Excel with pandas
    df = pd.read_excel(filepath, header=1)  # Row 2 has headers, row 1 ignored

    # TODO: Clean data (convert cost commas to dots, ensure numeric QTY)
    df['ITEM_COSTS'] = df['ITEM_COSTS'].astype(str).str.replace(',', '.').astype(float)
    df['SHP QTY'] = pd.to_numeric(df['SHP QTY'], errors='coerce').fillna(0).astype(int)

    # TODO: Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # TODO: Insert each row into the waybill_lines table
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO waybill_lines (
                waybill_number,
                part_number,
                qty_total,
                subinv,
                locator,
                description,
                item_cost,
                date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(row['Waybill']),
            str(row['ITEM']),
            int(row['SHP QTY']),
            str(row['SUBINV']),
            str(row['Locator']),
            str(row['DESCRIPTION']),
            float(row['ITEM_COSTS']),
            str(row['SHIP_DATE'])[:10]
        ))

    conn.commit()
    conn.close()
    print(f"Waybill '{filepath}' imported successfully.")