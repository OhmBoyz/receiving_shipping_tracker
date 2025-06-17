import argparse
import sqlite3


def add_active_column(db_path: str = "receiving_tracker.db") -> None:
    """Add `active` column to ``waybill_lines`` if missing."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(waybill_lines)")
    columns = [row[1] for row in cur.fetchall()]
    if "active" not in columns:
        cur.execute(
            "ALTER TABLE waybill_lines ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
        )
        conn.commit()

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add active column to waybill_lines")
    parser.add_argument("db_path", nargs="?", default="receiving_tracker.db")
    args = parser.parse_args()
    add_active_column(args.db_path)
    print("Migration complete")

