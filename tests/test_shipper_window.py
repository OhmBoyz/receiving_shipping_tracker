import sqlite3
import types

import pytest


from datetime import datetime, timedelta
from src.data_manager import DataManager


def setup_waybill(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    today = datetime.utcnow().date().isoformat()
    import_date = today
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        f" VALUES ('WB1', 'P1', 5, 'DRV-AMO', '', '', 0, '{today}', '{import_date}')"
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        f" VALUES ('WB1', 'P1', 10, 'DRV-RM', '', '', 0, '{today}', '{import_date}')"
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        f" VALUES ('WB2', 'P1', 5, 'DRV-AMO', '', '', 0, '{today}', '{import_date}')"
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

    cur = sqlite3.connect(temp_db).cursor()
    cur.execute('SELECT waybill_number FROM scan_sessions')
    session_waybill = cur.fetchone()[0]
    cur.connection.close()
    assert session_waybill == 'WB1'


def test_process_scan_lowercase_code(temp_db, monkeypatch):
    setup_waybill(temp_db)

    from src.ui import scanner_interface

    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    window.qty_var.set(1)
    window.scan_var.set('p1')
    window.process_scan()

    total_scanned = sum(l.scanned for l in window.lines)
    assert total_scanned == 1


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

    cur = sqlite3.connect(temp_db).cursor()
    cur.execute('SELECT waybill_number FROM scan_sessions WHERE session_id=?', (window.session_id,))
    current_wb = cur.fetchone()[0]
    cur.connection.close()
    assert current_wb == 'WB2'


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


def test_manual_logout_ends_session(temp_db, monkeypatch):
    setup_waybill(temp_db)

    from src.ui import scanner_interface

    monkeypatch.setattr(
        scanner_interface.messagebox,
        'askyesno',
        lambda *a, **kw: True,
        raising=False,
    )

    called = {'flag': False}

    orig = scanner_interface.ShipperWindow._finish_session

    def spy(self):
        called['flag'] = True
        orig(self)

    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', spy)

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    session_id = window.session_id
    assert session_id is not None

    window.manual_logout()

    assert called['flag'] is True

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT end_time FROM scan_sessions WHERE session_id=?', (session_id,))
    end_time = cur.fetchone()[0]
    conn.close()
    assert end_time is not None


def test_start_interface_with_blank_date(temp_db, monkeypatch):
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date) "
        "VALUES ('WBX', 'P1', 1, 'DRV-AMO', '', '', 0, '')"
    )
    conn.commit()
    conn.close()

    from src.ui import scanner_interface

    monkeypatch.setattr(
        scanner_interface.ShipperWindow,
        'mainloop',
        lambda self: None,
        raising=False,
    )

    # Should not raise TclError when waybill date missing
    scanner_interface.start_shipper_interface(1, temp_db)


def test_history_resets_between_sessions(temp_db, monkeypatch):
    setup_waybill(temp_db)

    from src.ui import scanner_interface

    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)

    win1 = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)
    win1.qty_var.set(1)
    win1.scan_var.set('P1')
    win1.process_scan()
    assert len(win1.last_entries) == 1

    win2 = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)
    assert win2.last_entries == []


def test_data_manager_helpers(temp_db):
    setup_waybill(temp_db)
    dm = DataManager(temp_db)
    progress = dm.get_waybill_progress()
    incompletes = dm.fetch_incomplete_waybills()
    assert incompletes == [row[0] for row in progress if row[2] > 0]
    rows = dm.get_waybill_lines_multi(['WB1', 'WB2'])
    assert len(rows) == 3


def test_progress_table_highlighting(temp_db, monkeypatch):
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    old_date = '2024-01-01'
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        " VALUES ('OLD1','P1',1,'DRV-AMO','','',0,?, ?)",
        (old_date, old_date),
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        " VALUES ('OLD2','P1',1,'DRV-AMO','','',0,?, ?)",
        (old_date, old_date),
    )
    conn.commit()
    conn.close()

    from src.ui import scanner_interface

    labels = []

    class RecLabel:
        def __init__(self, *a, **kw):
            labels.append((kw.get('text'), kw.get('text_color')))
        def grid(self, *a, **kw):
            pass
        def pack(self, *a, **kw):
            pass
        def cget(self, *a, **kw):
            return ''
        def configure(self, *a, **kw):
            pass

    monkeypatch.setattr(scanner_interface.ctk, 'CTkLabel', RecLabel)
    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)

    scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    orange = [c for t, c in labels if t and t.startswith('OLD')]
    assert all(c == 'orange' for c in orange)


def test_today_menu_empty_and_status_label(temp_db, monkeypatch):
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    old_date = '2000-01-01'
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date, import_date)"
        " VALUES ('OLDWB', 'P1', 1, 'DRV-AMO', '', '', 0, ?, ?)",
        (old_date, old_date),
    )
    conn.commit()
    conn.close()

    from src.ui import scanner_interface

    class RecOptionMenu:
        def __init__(self, *a, **kw):
            self.values = kw.get('values', [])
            self.variable = kw.get('variable')

        def grid(self, *a, **kw):
            pass

        def bind(self, *a, **kw):
            pass

        def configure(self, **kw):
            if 'values' in kw:
                self.values = kw['values']

        def cget(self, option):
            if option == 'values':
                return self.values
            return ''

    monkeypatch.setattr(scanner_interface.ctk, 'CTkOptionMenu', RecOptionMenu)
    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)
    assert window.waybill_var.get() == ''
    assert window.today_menu.values == []

    window._load_all_today()
    assert window.lines == []
    assert window.list_status._text == "Today's waybills"


def test_status_label_updates(temp_db, monkeypatch):
    setup_waybill(temp_db)

    from src.ui import scanner_interface

    monkeypatch.setattr(scanner_interface.ShipperWindow, '_finish_session', lambda self: None)

    window = scanner_interface.ShipperWindow(user_id=1, db_path=temp_db)

    window._load_all_today()
    assert window.list_status._text == "Today's waybills"

    window._load_all_incomplete()
    assert window.list_status._text == "Incomplete waybills"

    window._load_all_today()
    assert window.list_status._text == "Today's waybills"
