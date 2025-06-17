import sqlite3
from datetime import datetime

def setup_data(db_path: str) -> None:
    today = datetime.utcnow().date().isoformat()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date) "
        "VALUES ('WB1', 'P1', 5, 'DRV-AMO', '', '', 0, ?)",
        (today,),
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date) "
        "VALUES ('WB1', 'P1', 10, 'DRV-RM', '', '', 0, ?)",
        (today,),
    )
    cur.execute(
        "INSERT INTO scan_events (session_id, waybill_number, part_number, scanned_qty, timestamp, raw_scan) "
        "VALUES (1, 'WB1', 'P1', 6, ?, '')",
        (datetime.utcnow().isoformat(),),
    )
    conn.commit()
    conn.close()


def patch_window(monkeypatch, db_path):
    from src.ui import admin_interface

    monkeypatch.setattr(admin_interface.AdminWindow, "_build_summary_tab", lambda self: None)
    monkeypatch.setattr(admin_interface.AdminWindow, "_build_user_tab", lambda self: None)
    monkeypatch.setattr(admin_interface.AdminWindow, "_build_upload_tab", lambda self: None)
    monkeypatch.setattr(admin_interface.AdminWindow, "_build_db_tab", lambda self: None)
    return admin_interface.AdminWindow(db_path=db_path)


def test_load_waybill_table_allocates(temp_db, monkeypatch):
    from src.ui import admin_interface

    setup_data(temp_db)

    labels = []

    class RecLabel:
        def __init__(self, *a, **kw):
            labels.append(kw.get("text"))
        def pack(self, *a, **kw):
            pass
        def grid(self, *a, **kw):
            pass
        def configure(self, *a, **kw):
            pass
        def cget(self, *a, **kw):
            return ""
        def winfo_children(self):
            return []

    monkeypatch.setattr(admin_interface.ctk, "CTkLabel", RecLabel)

    win = patch_window(monkeypatch, temp_db)
    win._load_waybill_table("WB1")

    values = [v.get() for v, _, _ in sorted(win._wb_row_widgets.values(), key=lambda x: x[2])]
    assert values == ["0", "9"]
    assert labels[:3] == ["Part", "Remaining", "Remaining"]


def test_edit_waybill_allocates(monkeypatch, temp_db):
    from src.ui import admin_interface

    setup_data(temp_db)

    entries = []

    class RecEntry:
        def __init__(self, *a, **kw):
            entries.append(kw.get("textvariable"))
        def grid(self, *a, **kw):
            pass
        def pack(self, *a, **kw):
            pass

    class DummyTop:
        def __init__(self, *a, **kw):
            pass
        def grid(self, *a, **kw):
            pass
        def pack(self, *a, **kw):
            pass
        def destroy(self):
            pass

    monkeypatch.setattr(admin_interface.ctk, "CTkEntry", RecEntry)
    monkeypatch.setattr(admin_interface.ctk, "CTkToplevel", DummyTop, raising=False)

    win = patch_window(monkeypatch, temp_db)
    win._edit_waybill("WB1")

    values = [var.get() for var in entries]
    assert values == ["0", "9"]
