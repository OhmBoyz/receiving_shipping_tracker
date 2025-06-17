import sqlite3
from typing import Optional


def add_waybill_number_column(db_path: str = "receiving_tracker.db") -> None:
    """Add waybill_number columns to existing DB if they don't exist."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(scan_events)")
    columns = [row[1] for row in cur.fetchall()]
    if "waybill_number" not in columns:
        cur.execute("ALTER TABLE scan_events ADD COLUMN waybill_number TEXT NOT NULL DEFAULT ''")
        cur.execute(
            "UPDATE scan_events SET waybill_number=(SELECT waybill_number FROM scan_sessions WHERE scan_sessions.session_id=scan_events.session_id)"
        )
        conn.commit()

    cur.execute("PRAGMA table_info(scan_summary)")
    columns = [row[1] for row in cur.fetchall()]
    if "waybill_number" not in columns:
        cur.execute("ALTER TABLE scan_summary ADD COLUMN waybill_number TEXT NOT NULL DEFAULT ''")
        cur.execute(
            "UPDATE scan_summary SET waybill_number=(SELECT waybill_number FROM scan_sessions WHERE scan_sessions.session_id=scan_summary.session_id)"
        )
        conn.commit()

    cur.execute("PRAGMA table_info(waybill_lines)")
    columns = [row[1] for row in cur.fetchall()]
    if "import_date" not in columns:
        cur.execute("ALTER TABLE waybill_lines ADD COLUMN import_date TEXT NOT NULL DEFAULT (DATE('now'))")
        conn.commit()

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate database for waybill columns")
    parser.add_argument("db_path", nargs="?", default="receiving_tracker.db")
    args = parser.parse_args()
    add_waybill_number_column(args.db_path)
    print("Migration complete")
