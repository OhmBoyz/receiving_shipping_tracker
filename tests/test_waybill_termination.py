import sqlite3

from src.data_manager import DataManager


def setup_waybills(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB1', 'P1', 5, 'DRV-AMO', '', '', 0, '2024-01-01')"
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB2', 'P1', 5, 'DRV-AMO', '', '', 0, '2024-01-01')"
    )
    conn.commit()
    conn.close()


def test_terminated_table_created_and_insert(temp_db):
    dm = DataManager(temp_db)
    dm.mark_waybill_terminated("WB1", 1)

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='terminated_waybills'"
    )
    assert cur.fetchone() is not None
    cur.execute(
        "SELECT user_id FROM terminated_waybills WHERE waybill_number='WB1'"
    )
    assert cur.fetchone() == (1,)
    conn.close()


def test_fetch_waybills_excludes_terminated(temp_db):
    setup_waybills(temp_db)
    dm = DataManager(temp_db)
    dm.mark_waybill_terminated("WB1", 1)
    waybills = dm.fetch_waybills()
    assert waybills == ["WB2"]


def test_admin_window_terminate(monkeypatch, temp_db):
    setup_waybills(temp_db)
    called = {}

    def fake_mark(self, wb, uid):
        called["wb"] = wb
        called["uid"] = uid

    from src.ui import admin_interface

    monkeypatch.setattr(admin_interface.DataManager, "mark_waybill_terminated", fake_mark)
    monkeypatch.setattr(admin_interface.AdminWindow, "_build_summary_tab", lambda self: None)
    monkeypatch.setattr(admin_interface.AdminWindow, "_build_user_tab", lambda self: None)
    monkeypatch.setattr(admin_interface.AdminWindow, "_build_upload_tab", lambda self: None)
    monkeypatch.setattr(admin_interface.AdminWindow, "_build_db_tab", lambda self: None)

    win = admin_interface.AdminWindow(db_path=temp_db)
    win._select_waybill("WB1")
    win._terminate_selected_waybill()
    assert called["wb"] == "WB1"
