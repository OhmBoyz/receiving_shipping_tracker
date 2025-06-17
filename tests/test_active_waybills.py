import sqlite3
from src.data_manager import DataManager

def test_fetch_active_waybills(temp_db):
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE waybills (waybill_number TEXT, status TEXT)")
    cur.executemany(
        "INSERT INTO waybills (waybill_number, status) VALUES (?, ?)",
        [
            ("WB1", "ACTIVE"),
            ("WB2", "INACTIVE"),
            ("WB3", "active"),
        ],
    )
    conn.commit()
    conn.close()

    dm = DataManager(temp_db)
    result = dm.fetch_waybills(active_only=True)
    assert set(result) == {"WB1", "WB3"}
