import sqlite3

from src.data_manager import DataManager


def setup_waybill(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB1', 'P1', 5, 'DRV-AMO', '', '', 0, '2024-01-01')"
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB2', 'P2', 3, 'DRV-RM', '', '', 0, '2024-01-01')"
    )
    conn.commit()
    conn.close()


def test_mark_waybill_terminated_excludes_from_fetch(temp_db):
    setup_waybill(temp_db)
    dm = DataManager(temp_db)
    dm.mark_waybill_terminated('WB2', 1)
    waybills = dm.fetch_waybills()
    assert waybills == ['WB1']


def test_get_waybill_progress_excludes_terminated(temp_db):
    setup_waybill(temp_db)
    dm = DataManager(temp_db)
    dm.mark_waybill_terminated('WB2', 1)
    progress = dm.get_waybill_progress()
    wb_list = [wb for wb, _, _ in progress]
    assert wb_list == ['WB1']
