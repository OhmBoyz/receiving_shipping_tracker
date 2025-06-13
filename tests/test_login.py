import sqlite3

from src.ui import login
from src.data_manager import DataManager


def add_user(db_path, username='test', password='pw', role='ADMIN'):
    DataManager(db_path).create_user(username, password, role)


def test_authenticate_and_session_flow(temp_db):
    add_user(temp_db)

    user = login.authenticate_user('test', 'pw', temp_db)
    assert user is not None
    assert user[1] == 'test'

    session_id = login.create_session(user[0], temp_db)
    assert isinstance(session_id, int)

    login.end_session(session_id, temp_db)
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT end_time FROM scan_sessions WHERE session_id=?', (session_id,))
    end_time = cur.fetchone()[0]
    conn.close()
    assert end_time is not None


def test_create_session_with_waybill(temp_db):
    add_user(temp_db)

    user = login.authenticate_user('test', 'pw', temp_db)
    assert user is not None

    session_id = login.create_session(user[0], temp_db, 'WB1')
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT waybill_number FROM scan_sessions WHERE session_id=?', (session_id,))
    waybill = cur.fetchone()[0]
    conn.close()
    assert waybill == 'WB1'
