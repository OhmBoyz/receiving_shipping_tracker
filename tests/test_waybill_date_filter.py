import sqlite3

from src.data_manager import DataManager


def setup_waybills(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date) "
        "VALUES ('WB1', 'P1', 1, 'DRV-AMO', '', '', 0, '2024-01-01')"
    )
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date) "
        "VALUES ('WB2', 'P1', 1, 'DRV-AMO', '', '', 0, '2024-01-02')"
    )
    conn.commit()
    conn.close()


def test_fetch_waybills_date_filter(temp_db):
    setup_waybills(temp_db)
    dm = DataManager(temp_db)
    assert dm.fetch_waybills('2024-01-01') == ['WB1']
    assert sorted(dm.fetch_waybills()) == ['WB1', 'WB2']


def test_get_waybill_dates(temp_db):
    setup_waybills(temp_db)
    dm = DataManager(temp_db)
    dates = dm.get_waybill_dates()
    assert dates == {'WB1': '2024-01-01', 'WB2': '2024-01-02'}

