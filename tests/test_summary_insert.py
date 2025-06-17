import sqlite3
import pytest


from datetime import datetime, timedelta


def setup_waybill_multi(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    today = datetime.utcnow().date().isoformat()
    target = datetime.utcnow().date() - timedelta(days=1)
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    import_date = target.isoformat()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        f" VALUES ('WB1', 'P1', 5, 'DRV-AMO', '', '', 0, '{today}', '{import_date}')"
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        f" VALUES ('WB1', 'P2', 10, 'DRV-RM', '', '', 0, '{today}', '{import_date}')"
    )
    conn.commit()
    conn.close()


def test_record_summary_multiple_rows_single_call(temp_db, monkeypatch):
    setup_waybill_multi(temp_db)

    from src.ui import scanner_interface

    monkeypatch.setattr(scanner_interface.ShipperWindow, "_finish_session", lambda self: None)

    captured = []
    orig_insert = scanner_interface.DataManager.insert_scan_summaries

    def spy(self, rows):
        captured.append(list(rows))
        return orig_insert(self, rows)

    monkeypatch.setattr(scanner_interface.DataManager, "insert_scan_summaries", spy)
    monkeypatch.setattr(
        scanner_interface.DataManager,
        "insert_scan_summary",
        lambda *a, **kw: pytest.fail("single insert used"),
    )

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    window.qty_var.set(2)
    window.scan_var.set("P1")
    window.process_scan()

    window.qty_var.set(3)
    window.scan_var.set("P2")
    window.process_scan()

    window._record_summary()

    assert len(captured) == 1
    rows = captured[0]
    assert len(rows) == 2
    parts = {row[3]: row[4] for row in rows}
    assert parts["P1"] == 2
    assert parts["P2"] == 3

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT part_number, total_scanned FROM scan_summary ORDER BY part_number"
    )
    result = cur.fetchall()
    conn.close()
    assert result == [("P1", 2), ("P2", 3)]
