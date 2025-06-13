import sqlite3
import hashlib

from src.ui import login


def add_user(db_path, username='test', password='pw', role='ADMIN'):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, hashed, role),
    )
    conn.commit()
    conn.close()


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
