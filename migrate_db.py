# migrate_db.py

import sqlite3
import logging

# --- CONFIGURATION ---
# Make sure to rename your old database file to this name
OLD_DB_PATH = "old_receiving_tracker.db"
# This should be the name of your new database file
NEW_DB_PATH = "receiving_tracker.db"
# ---------------------

# A list of all the tables we need to copy
TABLES_TO_MIGRATE = [
    "users",
    "part_identifiers",
    "waybill_lines",
    "scan_sessions",
    "scan_events",
    "scan_summary",
    "terminated_waybills",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_table(old_cur, new_cur, table_name):
    """Copies all data from a specific table."""
    logging.info(f"Starting migration for table: {table_name}...")
    
    # Get all rows from the old table
    old_cur.execute(f"SELECT * FROM {table_name}")
    rows = old_cur.fetchall()
    
    if not rows:
        logging.info(f"Table '{table_name}' is empty, skipping.")
        return

    # Get column names from the old table
    old_cols = [description[0] for description in old_cur.description]
    
    # Get column names from the new table to handle schema changes
    new_cur.execute(f"PRAGMA table_info({table_name})")
    new_cols_info = new_cur.fetchall()
    new_cols = [info[1] for info in new_cols_info]

    # Build the INSERT statement dynamically
    placeholders = ", ".join("?" for _ in new_cols)
    query = f"INSERT INTO {table_name} ({', '.join(new_cols)}) VALUES ({placeholders})"
    
    migrated_rows = []
    for row in rows:
        row_dict = dict(zip(old_cols, row))
        # Create a new row tuple in the correct order for the new schema
        # If a column exists in the new schema but not the old, it will be None (or its default)
        new_row = tuple(row_dict.get(col_name) for col_name in new_cols)
        migrated_rows.append(new_row)

    # Insert all rows into the new table
    new_cur.executemany(query, migrated_rows)
    logging.info(f"Successfully migrated {len(migrated_rows)} rows into {table_name}.")


def main():
    """Main function to run the database migration."""
    logging.info("Starting database migration process.")
    
    try:
        old_conn = sqlite3.connect(OLD_DB_PATH)
        new_conn = sqlite3.connect(NEW_DB_PATH)
        
        old_cursor = old_conn.cursor()
        new_cursor = new_conn.cursor()

        for table in TABLES_TO_MIGRATE:
            try:
                migrate_table(old_cursor, new_cursor, table)
            except sqlite3.OperationalError as e:
                logging.error(f"Could not migrate table '{table}'. It might not exist in the old DB. Error: {e}")
                continue

        # Commit all changes to the new database
        new_conn.commit()
        logging.info("Migration complete! All data has been committed to the new database.")

    except sqlite3.Error as e:
        logging.error(f"A database error occurred: {e}")
    finally:
        if 'old_conn' in locals() and old_conn:
            old_conn.close()
        if 'new_conn' in locals() and new_conn:
            new_conn.close()
        logging.info("Database connections closed.")

if __name__ == "__main__":
    main()