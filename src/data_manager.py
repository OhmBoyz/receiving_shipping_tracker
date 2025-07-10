from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .config import DB_PATH


logger = logging.getLogger(__name__)


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

    def create_session(self, user_id: int, waybill: str = "") -> int:
        """Create a new scan session and return its id."""
        start_time = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO scan_sessions (user_id, waybill_number, start_time) VALUES (?, ?, ?)",
                (user_id, waybill, start_time),
            )
            conn.commit()
            session_id = cur.lastrowid
        assert session_id is not None
        return int(session_id)

    def end_session(self, session_id: int) -> None:
        """Mark ``session_id`` as finished."""
        end_time = datetime.now().isoformat()
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
            start_time = datetime.now().isoformat()
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

    # --- Generic helpers for admin DB viewer ----------------------------
    def fetch_table_names(self) -> List[str]:
        """Return a sorted list of user table names."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            return [r[0] for r in cur.fetchall()]

    def fetch_rows(self, table: str) -> Tuple[List[str], List[tuple]]:
        """Return column names and all rows from ``table`` including rowid."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            cols = [row[1] for row in cur.fetchall()]
            cur.execute(f"SELECT rowid, * FROM {table}")
            rows = cur.fetchall()
        return ["rowid", *cols], rows

    def update_row(
        self,
        table: str,
        pk: int,
        data: Dict[str, object],
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        """Update ``table`` row identified by ``pk`` using ``data``."""
        close = False
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            close = True
        cur = conn.cursor()
        columns = ", ".join(f"{col}=?" for col in data.keys())
        params = list(data.values()) + [pk]
        cur.execute(f"UPDATE {table} SET {columns} WHERE rowid=?", params)
        if close:
            conn.commit()
            conn.close()

    def delete_row(
        self, table: str, pk: int, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Delete row ``pk`` from ``table``."""
        close = False
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            close = True
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table} WHERE rowid=?", (pk,))
        if close:
            conn.commit()
            conn.close()

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

    def mark_waybill_terminated(self, waybill: str, user_id: int) -> None:
        """Record ``waybill`` termination by ``user_id`` with timestamp."""
        terminated_at = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO terminated_waybills "
                "(waybill_number, terminated_at, user_id) VALUES (?, ?, ?)",
                (waybill, terminated_at, user_id),
            )
            conn.commit()
        logger.info("Waybill %s terminated by user %s", waybill, user_id)

    # --- Waybill / scanning queries ------------------------------------
    def fetch_waybills(self, date: str | None = None) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            query = (
                "SELECT DISTINCT waybill_number FROM waybill_lines "
                "WHERE waybill_number NOT IN (SELECT waybill_number FROM terminated_waybills)"
            )
            params: list[str] = []
            if date:
                query += " AND date=?"
                params.append(date)
            cur.execute(query, params)
            rows = [r[0] for r in cur.fetchall()]
        return rows

    def fetch_incomplete_waybills(self) -> List[str]:
        """Return active waybills that still have remaining quantity."""
        progress = self.get_waybill_progress()
        return [wb for wb, _, remaining in progress if remaining > 0]

    def get_waybill_dates(self) -> Dict[str, str]:
        """Return mapping of active waybills to their reception date."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT waybill_number, date FROM waybill_lines "
                "WHERE waybill_number NOT IN (SELECT waybill_number FROM terminated_waybills)"
            )
            rows = {row[0]: row[1] for row in cur.fetchall()}
        return rows

    def get_waybill_import_dates(self) -> Dict[str, str]:
        """Return mapping of active waybills to their import date."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT waybill_number, import_date FROM waybill_lines "
                "WHERE waybill_number NOT IN (SELECT waybill_number FROM terminated_waybills)"
            )
            rows = {row[0]: row[1] for row in cur.fetchall()}
        return rows

    def fetch_scans(self, waybill: str) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT part_number, SUM(scanned_qty) FROM scan_events WHERE UPPER(waybill_number)=UPPER(?) GROUP BY part_number",
                (waybill,),
            )
            data = {row[0]: int(row[1]) for row in cur.fetchall()}
        return data

    def get_waybill_progress(self) -> List[Tuple[str, int, int]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT waybill_number, SUM(qty_total) FROM waybill_lines "
                "WHERE waybill_number NOT IN (SELECT waybill_number FROM terminated_waybills) "
                "GROUP BY waybill_number"
            )
            totals = {row[0]: int(row[1]) for row in cur.fetchall()}
            cur.execute(
                "SELECT waybill_number, SUM(scanned_qty) FROM scan_events "
                "WHERE waybill_number NOT IN (SELECT waybill_number FROM terminated_waybills) "
                "GROUP BY waybill_number"
            )
            scanned = {row[0]: int(row[1]) for row in cur.fetchall()}
        progress = []
        for wb, total in totals.items():
            done = scanned.get(wb, 0)
            remaining = max(total - done, 0)
            progress.append((wb, total, remaining))
        progress.sort()
        return progress

    def get_waybill_lines(self, waybill: str) -> List[Tuple[int, str, int, str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, part_number, qty_total, subinv, waybill_number FROM waybill_lines WHERE UPPER(waybill_number)=UPPER(?) ORDER BY part_number",
                (waybill,),
            )
            rows = [(int(r[0]), r[1], int(r[2]), r[3], r[4]) for r in cur.fetchall()]
        return rows

    def get_waybill_lines_multi(self, waybills: Iterable[str]) -> List[Tuple[int, str, int, str, str]]:
        """Return lines for all ``waybills``."""
        ids = list(waybills)
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        query = (
            f"SELECT id, part_number, qty_total, subinv, waybill_number FROM waybill_lines WHERE waybill_number IN ({placeholders}) ORDER BY waybill_number, part_number"
        )
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(query, ids)
            rows = [(int(r[0]), r[1], int(r[2]), r[3], r[4]) for r in cur.fetchall()]
        return rows

    def insert_scan_event(
        self,
        session_id: int,
        waybill_number: str,
        part_number: str,
        qty: int,
        timestamp: Optional[str] = None,
        raw_scan: str = "",
        allocation_details: str = "",
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO scan_events (session_id, waybill_number, part_number, scanned_qty, timestamp, raw_scan, allocation_details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, waybill_number, part_number, qty, timestamp, raw_scan, allocation_details),
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
        self.insert_scan_summaries(
            [
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
                )
            ]
        )

    def insert_scan_summaries(self, rows: Iterable[tuple]) -> None:
        """Insert multiple scan summary rows in a single transaction."""
        rows = list(rows)
        if not rows:
            return
        query = (
            "INSERT INTO scan_summary (session_id, waybill_number, user_id, part_number, total_scanned, expected_qty, remaining_qty, allocated_to, reception_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.executemany(query, rows)
            conn.commit()

    def resolve_part(self, code: str) -> Tuple[str, int]:
        code = code.strip().upper()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT part_number, qty FROM part_identifiers WHERE UPPER(part_number)=? OR UPPER(upc_code)=?",
                    (code, code),
                )
                row = cur.fetchone()
            except sqlite3.OperationalError:
                cur.execute(
                    "SELECT part_number FROM part_identifiers WHERE UPPER(part_number)=? OR UPPER(upc_code)=?",
                    (code, code),
                )
                result = cur.fetchone()
                row = (result[0], 1) if result else None
        if row:
            part, qty = row[0].upper(), row[1]
            qty = int(qty) if qty is not None else 1
            return part, qty
        # not found in DB
        return code, 1

    # --- Part identifiers -----------------------------------------------
    def insert_part_identifiers(self, rows: Iterable[tuple]) -> int:
        """Insert multiple part identifier rows and return number inserted."""
        rows = list(rows)
        if not rows:
            return 0
        query = (
            "INSERT INTO part_identifiers (part_number, upc_code, qty, description) "
            "VALUES (?, ?, ?, ?)"
        )
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.executemany(query, rows)
            conn.commit()
            return cur.rowcount if cur.rowcount != -1 else len(rows)

    def clear_part_identifiers(self) -> None:
        """Remove all rows from ``part_identifiers`` table."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM part_identifiers")
            conn.commit()

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
                "FROM scan_summary s LEFT JOIN users u ON u.user_id = s.user_id WHERE 1=1"
            )
            params: List[object] = []
            if user_id is not None:
                query += " AND s.user_id=?"
                params.append(user_id)
            if date:
                query += " AND s.reception_date=?"
                params.append(date)
            if waybill:
                query += " AND UPPER(s.waybill_number)=UPPER(?)"
                params.append(waybill)
            cur.execute(query, params)
            rows = cur.fetchall()
        return rows
    
    def insert_bo_items(self, items: Iterable[Dict[str, any]]) -> Tuple[int, int]:
        """
        Insert or update records in the bo_items table, preserving fulfillment status.
        """
        created = 0
        updated = 0
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            for item in items:
                cur.execute(
                    "SELECT id, pick_status, qty_fulfilled FROM bo_items WHERE go_item = ? AND part_number = ?",
                    (item["go_item"], item["part_number"]),
                )
                existing = cur.fetchone()
                if existing:
                    # Preserve existing status and fulfilled quantity
                    item["pick_status"] = existing[1]
                    item["qty_fulfilled"] = existing[2]

                    # Ensure qty_fulfilled is not greater than the new required qty
                    if item["qty_fulfilled"] > item["qty_req"]:
                        item["qty_fulfilled"] = item["qty_req"]

                    update_cols = ", ".join(f"{key} = ?" for key in item)
                    params = list(item.values()) + [existing[0]]
                    cur.execute(f"UPDATE bo_items SET {update_cols} WHERE id = ?", params)
                    updated += 1
                else:
                    # Insert new record
                    cols = ", ".join(item.keys())
                    placeholders = ", ".join("?" for _ in item)
                    params = list(item.values())
                    cur.execute(f"INSERT INTO bo_items ({cols}) VALUES ({placeholders})", params)
                    created += 1
            conn.commit()
        return created, updated
    
    def get_open_bo_lines(self, part_number: str) -> List[Tuple[int, str, int, int]]:
        """
        Fetches all open back-order lines for a part number.
        Returns a list of tuples: [(id, go_item, qty_req, qty_fulfilled), ...].
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, go_item, qty_req, qty_fulfilled FROM bo_items WHERE part_number = ? AND pick_status = 'NOT_STARTED' ORDER BY redcon_status",
                (part_number.upper(),),
            )
            return cur.fetchall()

    def update_bo_item_status(self, bo_item_id: int, status: str) -> None:
        """Update the pick_status of a specific back-order item."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE bo_items SET pick_status = ? WHERE id = ?",
                (status, bo_item_id),
            )
            conn.commit()

    def get_session_allocations(self, session_id: int) -> Dict[str, str]:
        """
        Aggregates allocation details from a session for each part.
        Returns a dictionary mapping {part_number: "allocation_string"}.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT part_number, allocation_details FROM scan_events WHERE session_id = ? AND allocation_details IS NOT NULL",
                (session_id,)
            )

            part_allocations = {}
            for part_number, details_str in cur.fetchall():
                # The details are stored as '{"BO": 14, "KANBAN": 46}'
                # We need to parse this and aggregate it.
                import json
                try:
                    details = json.loads(details_str)
                except (json.JSONDecodeError, TypeError):
                    continue

                if part_number not in part_allocations:
                    part_allocations[part_number] = {}

                for key, value in details.items():
                    part_allocations[part_number][key] = part_allocations[part_number].get(key, 0) + value

            # Convert the aggregated dicts into final strings
            final_strings = {}
            for part, alloc_dict in part_allocations.items():
                final_strings[part] = ", ".join([f"{k}:{v}" for k, v in alloc_dict.items()])

            return final_strings
    
    def clear_non_picking_bo_items(self) -> int:
        """
        Deletes all BO items that are NOT in a 'PICKING' state.
        This is the pre-import cleanup step.
        Returns the number of rows deleted.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM bo_items WHERE pick_status != 'PICKING'")
            deleted_count = cur.rowcount
            conn.commit()
        return deleted_count if deleted_count != -1 else 0

    def reconcile_picking_items(self, active_keys: List[Tuple[str, str]]) -> int:
        """
        Deletes 'PICKING' items that are no longer in the active report.
        This is the post-import cleanup step.
        Returns the number of rows deleted.
        """
        if not active_keys:
            # If there are no active keys, all 'PICKING' items are stale.
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM bo_items WHERE pick_status = 'PICKING'")
                return cur.rowcount if cur.rowcount != -1 else 0

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # Create a temporary table of active keys for efficient lookup
            cur.execute("CREATE TEMP TABLE active_bo_keys (go_item TEXT, part_number TEXT, PRIMARY KEY(go_item, part_number))")
            cur.executemany("INSERT INTO active_bo_keys (go_item, part_number) VALUES (?, ?)", active_keys)
            
            # Delete PICKING items that are not in the active list
            cur.execute("""
                DELETE FROM bo_items
                WHERE pick_status = 'PICKING' 
                AND (go_item, part_number) NOT IN (SELECT go_item, part_number FROM active_bo_keys)
            """)
            deleted_count = cur.rowcount
            conn.commit()

        return deleted_count if deleted_count != -1 else 0
    
    def update_bo_fulfillment(self, bo_item_id: int, newly_fulfilled_qty: int) -> None:
        """
        Atomically increments the qty_fulfilled for a specific back-order item.
        This method does NOT change the pick_status.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # Only increment the fulfilled quantity. The status is handled later.
            cur.execute(
                "UPDATE bo_items SET qty_fulfilled = qty_fulfilled + ? WHERE id = ?",
                (newly_fulfilled_qty, bo_item_id),
            )
            conn.commit()


    def get_next_urgent_picklist_items(self) -> List[Dict]:
        """
        Finds the most urgent 'go_item' with 'NOT_STARTED' parts and returns
        all lines associated with it for picklist generation.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Use a row factory to get dictionary-like results
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Step 1: Find the single most urgent go_item
            cur.execute("""
                SELECT go_item
                FROM bo_items
                WHERE pick_status = 'NOT_STARTED'
                ORDER BY redcon_status ASC, id ASC
                LIMIT 1
            """)
            result = cur.fetchone()
            if not result:
                return []  # No items are waiting to be picked

            most_urgent_go_item = result["go_item"]

            # Step 2: Fetch all lines for that specific go_item
            cur.execute(
                "SELECT * FROM bo_items WHERE go_item = ?",
                (most_urgent_go_item,)
            )
            
            # Convert rows to standard dictionaries
            rows = [dict(row) for row in cur.fetchall()]
            return rows
    
    def get_urgent_go_numbers(self) -> List[Tuple[str, int]]:
        """Gets a list of unique GO numbers that have items in 'NOT_STARTED' status, ordered by urgency."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # This query finds the highest urgency (lowest redcon_status) for each GO group
            # that contains at least one 'NOT_STARTED' item.
            cur.execute("""
                SELECT go_num, MIN(redcon_status) as top_urgency
                FROM (
                    SELECT SUBSTR(go_item, 1, INSTR(go_item, '-') - 1) as go_num, redcon_status
                    FROM bo_items
                    WHERE pick_status = 'NOT_STARTED'
                )
                GROUP BY go_num
                ORDER BY top_urgency ASC
            """)
            return cur.fetchall()
    
    def update_bo_items_status(self, item_ids: List[int], status: str) -> None:
        """Updates the pick_status for a list of bo_item IDs."""
        if not item_ids:
            return
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # Creates a list of tuples for executemany, e.g., [('IN_PROGRESS', 1), ('IN_PROGRESS', 2)]
            params = [(status, item_id) for item_id in item_ids]
            cur.executemany("UPDATE bo_items SET pick_status = ? WHERE id = ?", params)
            conn.commit()

    def get_all_items_for_go(self, go_number: str) -> List[Dict]:
        """Fetches all bo_items for a given GO number prefix."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM bo_items WHERE go_item LIKE ?",
                (f"{go_number}-%",)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_inprogress_go_numbers(self) -> List[Tuple[str, int]]:
        """Gets a list of unique GO numbers that have items in 'IN_PROGRESS' status."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT go_num, MIN(redcon_status) as top_urgency
                FROM (
                    SELECT SUBSTR(go_item, 1, INSTR(go_item, '-') - 1) as go_num, redcon_status
                    FROM bo_items
                    WHERE pick_status = 'IN_PROGRESS'
                )
                WHERE go_num NOT IN (SELECT SUBSTR(go_item, 1, INSTR(go_item, '-') - 1) FROM bo_items WHERE pick_status = 'NOT_STARTED')
                GROUP BY go_num
                ORDER BY top_urgency ASC
            """)
            return cur.fetchall()

    def get_go_number_status_summary(self, go_number: str) -> Dict[str, int]:
        """
        Returns a dictionary summarizing the pick_status counts for a given GO number.
        e.g., {'NOT_STARTED': 5, 'IN_PROGRESS': 2}
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT pick_status, COUNT(*) FROM bo_items WHERE go_item LIKE ? GROUP BY pick_status",
                (f"{go_number}-%",)
            )
            return dict(cur.fetchall())
    
    def get_inprogress_lines_for_go(self, go_number: str) -> List[Dict]:
        """Fetches all lines for a GO number that are IN_PROGRESS and not yet complete."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Find lines that are part of an active picklist but not yet fully fulfilled
            cur.execute(
                "SELECT * FROM bo_items WHERE go_item LIKE ? AND pick_status = 'IN_PROGRESS' AND qty_fulfilled < qty_req ORDER BY item_number",
                (f"{go_number}-%",)
            )
            return [dict(row) for row in cur.fetchall()]
    
    def batch_update_bo_fulfillment(self, updates: List[Tuple[int, int]]) -> None:
        """
        Takes a list of (bo_item_id, picked_qty) and updates fulfillment.
        Sets status to COMPLETED if fully fulfilled.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            for bo_item_id, picked_qty in updates:
                # Increment the fulfilled quantity
                cur.execute(
                    "UPDATE bo_items SET qty_fulfilled = qty_fulfilled + ? WHERE id = ?",
                    (picked_qty, bo_item_id),
                )
            
            # After all updates, check which lines are now complete
            # Get all IDs that were just updated
            updated_ids = tuple(item[0] for item in updates)
            cur.execute(
                f"SELECT id FROM bo_items WHERE id IN ({','.join('?' for _ in updated_ids)}) AND qty_fulfilled >= qty_req",
                updated_ids
            )
            completed_ids = [row[0] for row in cur.fetchall()]
            
            # Update status for completed items
            if completed_ids:
                cur.executemany(
                    "UPDATE bo_items SET pick_status = 'COMPLETED' WHERE id = ?",
                    [(cid,) for cid in completed_ids]
                )
            conn.commit()