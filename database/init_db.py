import sqlite3

def initialize_database(db_path='receiving_tracker.db', schema_path='database/schema.sql'):
    with open(schema_path, 'r') as schema_file:
        schema = schema_file.read()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Database created and initialized at '{db_path}'")

if __name__ == '__main__':
    initialize_database()
