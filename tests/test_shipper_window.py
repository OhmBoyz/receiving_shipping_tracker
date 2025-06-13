import sqlite3
import types

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
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB2', 'P1', 5, 'DRV-AMO', '', '', 0, '2024-01-01')"
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
    cur.execute('SELECT scanned_qty, waybill_number FROM scan_events')
    qty, waybill = cur.fetchone()
    conn.close()
    assert qty == 6
    assert waybill == 'WB1'


def test_waybill_switch_does_not_affect_previous_scans(temp_db, monkeypatch):
    setup_waybill(temp_db)

    from src.ui import scanner_interface

    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    window.qty_var.set(2)
    window.scan_var.set('P1')
    window.process_scan()

    # switch to second waybill and scan again
    window.waybill_var.set('WB2')
    window.load_waybill('WB2')
    window.qty_var.set(3)
    window.scan_var.set('P1')
    window.process_scan()

    # verify scans for WB1 remain
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT SUM(scanned_qty) FROM scan_events WHERE waybill_number=?', ('WB1',))
    wb1_qty = cur.fetchone()[0]
    cur.execute('SELECT SUM(scanned_qty) FROM scan_events WHERE waybill_number=?', ('WB2',))
    wb2_qty = cur.fetchone()[0]
    conn.close()

    assert wb1_qty == 2
    assert wb2_qty == 3

    progress = window._get_waybill_progress()
    remaining_dict = {wb: rem for wb, _, rem in progress}
    assert remaining_dict['WB1'] == 13
    assert remaining_dict['WB2'] == 2


def test_overscan_aborts_without_recording(temp_db, monkeypatch):
    setup_waybill(temp_db)

    from src.ui import scanner_interface

    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)
    monkeypatch.setattr(
        scanner_interface,
        'messagebox',
        types.SimpleNamespace(
            showinfo=lambda *a, **kw: None,
            showwarning=lambda *a, **kw: None,
            showerror=lambda *a, **kw: None,
        ),
    )
    alerted = {'called': False}

    def fake_beep(self):
        alerted['called'] = True

    monkeypatch.setattr(scanner_interface.ShipperWindow, '_alert_beep', fake_beep)

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    window.qty_var.set(20)
    window.scan_var.set('P1')
    window.process_scan()

    for line in window.lines:
        assert line.scanned == 0

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM scan_events')
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0
    assert alerted['called'] is True
