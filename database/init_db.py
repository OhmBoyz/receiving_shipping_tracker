import sqlite3
import logging

from src.logging_utils import setup_logging

#def initialize_database(db_path='receiving_tracker.db', schema_path='database/schema.sql'):
setup_logging()
logger = logging.getLogger(__name__)


def initialize_database(
    db_path: str = "receiving_tracker.db",
    schema_path: str = "database/schema.sql",
) -> None:
    with open(schema_path, 'r') as schema_file:
        schema = schema_file.read()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    logger.info("Database created and initialized at '%s'", db_path)

if __name__ == '__main__':
    initialize_database()
