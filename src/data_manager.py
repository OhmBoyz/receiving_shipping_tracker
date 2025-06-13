from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .config import DB_PATH


class DataManager:
    """Simple wrapper for all database interactions."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    # --- User authentication & sessions ---------------------------------
    def authenticate_user(self, username: str, password: str) -> Optional[Tuple[int, str, str]]:
        """Return (user_id, username, role) if credentials are valid."""
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, username, role FROM users WHERE username=? AND password_hash=?",
                (username, hashed_pw),
            )
            return cur.fetchone()  # type: ignore[return-value]

    def create_session(self, user_id: int) -> int:
        """Create a new scan session and return its id."""
        start_time = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO scan_sessions (user_id, waybill_number, start_time) VALUES (?, ?, ?)",
                (user_id, "", start_time),
            )
            conn.commit()
            session_id = cur.lastrowid
        assert session_id is not None
        return int(session_id)

    def end_session(self, session_id: int) -> None:
        """Mark ``session_id`` as finished."""
        end_time = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE scan_sessions SET end_time=? WHERE session_id=?",
                (end_time, session_id),
            )
            conn.commit()

    def get_or_create_session(self, user_id: int) -> int:
        """Return the latest open session for ``user_id`` or create one."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT session_id FROM scan_sessions WHERE user_id=? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                return int(row[0])
            start_time = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO scan_sessions (user_id, waybill_number, start_time) VALUES (?, ?, ?)",
                (user_id, "", start_time),
            )
            conn.commit()
            session_id = cur.lastrowid or 0
        return int(session_id)

    def update_session_waybill(self, session_id: int, waybill: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE scan_sessions SET waybill_number=? WHERE session_id=?",
                (waybill, session_id),
            )
            conn.commit()

    # --- User CRUD ------------------------------------------------------
    def get_users(self) -> List[Tuple[int, str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id, username, role FROM users ORDER BY username")
            rows = [(int(r[0]), r[1], r[2]) for r in cur.fetchall()]
        return rows

    def create_user(self, username: str, password: str, role: str) -> None:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, hashed, role),
            )
            conn.commit()

    def update_user(self, user_id: int, username: str, role: str, password: Optional[str] = None) -> None:
        hashed = hashlib.sha256(password.encode()).hexdigest() if password else None
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            if hashed:
                cur.execute(
                    "UPDATE users SET username=?, role=?, password_hash=? WHERE user_id=?",
                    (username, role, hashed, user_id),
                )
            else:
                cur.execute(
                    "UPDATE users SET username=?, role=? WHERE user_id=?",
                    (username, role, user_id),
                )
            conn.commit()

    def delete_user(self, user_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()

    # --- Waybill / scanning queries ------------------------------------
    def fetch_waybills(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT waybill_number FROM waybill_lines")
            rows = [r[0] for r in cur.fetchall()]
        return rows

    def fetch_scans(self, waybill: str) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT part_number, SUM(scanned_qty) FROM scan_events WHERE waybill_number=? GROUP BY part_number",
                (waybill,),
            )
            data = {row[0]: int(row[1]) for row in cur.fetchall()}
        return data

    def get_waybill_progress(self) -> List[Tuple[str, int, int]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT waybill_number, SUM(qty_total) FROM waybill_lines GROUP BY waybill_number"
            )
            totals = {row[0]: int(row[1]) for row in cur.fetchall()}
            cur.execute(
                "SELECT waybill_number, SUM(scanned_qty) FROM scan_events GROUP BY waybill_number"
            )
            scanned = {row[0]: int(row[1]) for row in cur.fetchall()}
        progress = []
        for wb, total in totals.items():
            done = scanned.get(wb, 0)
            remaining = max(total - done, 0)
            progress.append((wb, total, remaining))
        progress.sort()
        return progress

    def get_waybill_lines(self, waybill: str) -> List[Tuple[int, str, int, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, part_number, qty_total, subinv FROM waybill_lines WHERE waybill_number=? ORDER BY part_number",
                (waybill,),
            )
            rows = [(int(r[0]), r[1], int(r[2]), r[3]) for r in cur.fetchall()]
        return rows

    def insert_scan_event(
        self,
        session_id: int,
        waybill_number: str,
        part_number: str,
        qty: int,
        timestamp: Optional[str] = None,
        raw_scan: str = "",
    ) -> None:
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO scan_events (session_id, waybill_number, part_number, scanned_qty, timestamp, raw_scan) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, waybill_number, part_number, qty, timestamp, raw_scan),
            )
            conn.commit()

    def insert_scan_summary(
        self,
        session_id: int,
        waybill_number: str,
        user_id: int,
        part_number: str,
        total_scanned: int,
        expected_qty: int,
        remaining_qty: int,
        allocated_to: str,
        reception_date: str,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO scan_summary (session_id, waybill_number, user_id, part_number, total_scanned, expected_qty, remaining_qty, allocated_to, reception_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    waybill_number,
                    user_id,
                    part_number,
                    total_scanned,
                    expected_qty,
                    remaining_qty,
                    allocated_to,
                    reception_date,
                ),
            )
            conn.commit()

    def resolve_part(self, code: str) -> Tuple[str, int]:
        code = code.strip()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT part_number, qty FROM part_identifiers WHERE part_number=? OR upc_code=?",
                    (code, code),
                )
                row = cur.fetchone()
            except sqlite3.OperationalError:
                cur.execute(
                    "SELECT part_number FROM part_identifiers WHERE part_number=? OR upc_code=?",
                    (code, code),
                )
                result = cur.fetchone()
                row = (result[0], 1) if result else None
        if row:
            part, qty = row[0], row[1]
            qty = int(qty) if qty is not None else 1
            return part, qty
        # not found in DB
        return code, 1

    # --- Scan summaries -------------------------------------------------
    def query_scan_summary(
        self,
        user_id: Optional[int] = None,
        date: Optional[str] = None,
        waybill: Optional[str] = None,
    ) -> List[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            query = (
                "SELECT s.waybill_number, u.username, s.part_number, s.total_scanned, "
                "s.expected_qty, s.remaining_qty, s.allocated_to, s.reception_date "
                "FROM scan_summary s JOIN users u ON u.user_id = s.user_id WHERE 1=1"
            )
            params: List[object] = []
            if user_id is not None:
                query += " AND s.user_id=?"
                params.append(user_id)
            if date:
                query += " AND s.reception_date=?"
                params.append(date)
            if waybill:
                query += " AND s.waybill_number=?"
                params.append(waybill)
            cur.execute(query, params)
            rows = cur.fetchall()
        return rows
