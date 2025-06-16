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
