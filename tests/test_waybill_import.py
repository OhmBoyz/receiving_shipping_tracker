import sqlite3
from src.logic import waybill_import


def test_import_waybill(temp_db):
    inserted = waybill_import.import_waybill('data/wb sample.xlsx', temp_db)
    assert inserted == 18

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM waybill_lines')
    count = cur.fetchone()[0]
    conn.close()
    assert count == 18
