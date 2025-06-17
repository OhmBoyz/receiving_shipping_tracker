import sqlite3

from src.data_manager import DataManager


def test_table_listing(temp_db):
    dm = DataManager(temp_db)
    tables = dm.fetch_table_names()
    assert 'users' in tables
    assert 'waybill_lines' in tables


def test_row_crud(temp_db):
    dm = DataManager(temp_db)
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('u1','h','ADMIN')"
    )
    conn.commit()
    conn.close()

    cols, rows = dm.fetch_rows('users')
    assert cols[1:] == ['user_id', 'username', 'password_hash', 'role'] or cols[0] == 'rowid'
    pk = rows[0][0]

    dm.update_row('users', pk, {'username': 'u2'})
    cols, rows = dm.fetch_rows('users')
    assert rows[0][cols.index('username')] == 'u2'

    dm.delete_row('users', pk)
    _, rows = dm.fetch_rows('users')
    assert rows == []


def test_waybill_inactive_filter(temp_db):
    dm = DataManager(temp_db)
    conn = sqlite3.connect(temp_db)
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

    dm.mark_waybill_inactive('WB2')
    waybills = dm.fetch_waybills()
    assert 'WB1' in waybills and 'WB2' not in waybills
    progress = dm.get_waybill_progress()
    names = [wb for wb, _, _ in progress]
    assert 'WB2' not in names
