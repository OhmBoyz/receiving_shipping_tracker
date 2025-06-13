-- users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT CHECK(role IN ('ADMIN', 'SHIPPER')) NOT NULL
);

-- part_identifiers
CREATE TABLE IF NOT EXISTS part_identifiers (
    part_number TEXT PRIMARY KEY,
    upc_code TEXT UNIQUE,
    qty TEXT,
    description TEXT
);

-- waybill_lines
CREATE TABLE IF NOT EXISTS waybill_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waybill_number TEXT NOT NULL,
    part_number TEXT NOT NULL,
    qty_total INTEGER NOT NULL,
    subinv TEXT NOT NULL,
    locator TEXT,
    description TEXT,
    item_cost REAL,
    date TEXT NOT NULL
);

-- scan_sessions
CREATE TABLE IF NOT EXISTS scan_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    waybill_number TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

-- scan_events
CREATE TABLE IF NOT EXISTS scan_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    part_number TEXT NOT NULL,
    scanned_qty INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    raw_scan TEXT,
    FOREIGN KEY(session_id) REFERENCES scan_sessions(session_id)
);

-- scan_summary
CREATE TABLE IF NOT EXISTS scan_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    part_number TEXT NOT NULL,
    total_scanned INTEGER,
    expected_qty INTEGER,
    remaining_qty INTEGER,
    allocated_to TEXT,
    reception_date TEXT,
    FOREIGN KEY(session_id) REFERENCES scan_sessions(session_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
