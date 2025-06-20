import sqlite3
from datetime import datetime

from src.data_manager import DataManager


def setup_summaries(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # create one valid user and session
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('u1','h','ADMIN')"
    )
    uid = cur.lastrowid
    cur.execute(
        "INSERT INTO scan_sessions (user_id, waybill_number, start_time) VALUES (?,?,?)",
        (uid, 'WB1', datetime.now().isoformat()),
    )
    sess1 = cur.lastrowid
    today = datetime.now().date().isoformat()
    cur.execute(
        "INSERT INTO scan_summary (session_id, waybill_number, user_id, part_number, total_scanned, expected_qty, remaining_qty, allocated_to, reception_date) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (sess1, 'WB1', uid, 'P1', 1, 1, 0, '', today),
    )

    # summary row with no matching user
    cur.execute(
        "INSERT INTO scan_sessions (user_id, waybill_number, start_time) VALUES (?,?,?)",
        (99, 'WB2', datetime.now().isoformat()),
    )
    sess2 = cur.lastrowid
    cur.execute(
        "INSERT INTO scan_summary (session_id, waybill_number, user_id, part_number, total_scanned, expected_qty, remaining_qty, allocated_to, reception_date) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (sess2, 'WB2', 99, 'P2', 2, 2, 0, '', today),
    )
    conn.commit()
    conn.close()


def test_query_scan_summary_includes_unknown_user(temp_db):
    setup_summaries(temp_db)
    dm = DataManager(temp_db)
    rows = dm.query_scan_summary()
    waybills = {r[0] for r in rows}
    assert {'WB1', 'WB2'} == waybills
