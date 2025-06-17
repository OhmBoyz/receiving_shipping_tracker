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


def test_waybill_complete_flow(temp_db):
    setup_waybill(temp_db)
    dm = DataManager(temp_db)

    active = dm.fetch_active_waybills()
    assert sorted(active) == ['WB1', 'WB2']

    dm.mark_waybill_completed('WB1')

    active_after = dm.fetch_active_waybills()
    assert active_after == ['WB2']
