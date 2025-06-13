import sqlite3

import pytest


def setup_waybill(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB1', 'P1', 5, 'DRV-AMO', '', '', 0, '2024-01-01')"
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB1', 'P1', 10, 'DRV-RM', '', '', 0, '2024-01-01')"
    )
    conn.commit()
    conn.close()


def test_process_scan_allocation(temp_db, monkeypatch):
    setup_waybill(temp_db)

    # Import here after dummy_gui fixture patched customtkinter
    from src.ui import scanner_interface

    # patch finish_session to avoid touching GUI
    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    # Set quantity and scan code
    window.qty_var.set(6)
    window.scan_var.set('P1')
    window.process_scan()

    amoline = [l for l in window.lines if 'AMO' in l.subinv][0]
    kanbanline = [l for l in window.lines if 'AMO' not in l.subinv][0]
    assert amoline.scanned == 5
    assert kanbanline.scanned == 1

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT scanned_qty FROM scan_events')
    qty = cur.fetchone()[0]
    conn.close()
    assert qty == 6
