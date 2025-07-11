-- users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT CHECK(role IN ('ADMIN', 'SHIPPER')) NOT NULL
);

-- part_identifiers
CREATE TABLE IF NOT EXISTS part_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_number TEXT NOT NULL,
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
    date TEXT NOT NULL,
    import_date TEXT NOT NULL DEFAULT (DATE('now'))
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
    waybill_number TEXT NOT NULL DEFAULT '',
    part_number TEXT NOT NULL,
    scanned_qty INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    raw_scan TEXT,
    allocation_details TEXT, 
    FOREIGN KEY(session_id) REFERENCES scan_sessions(session_id)
);

-- scan_summary
CREATE TABLE IF NOT EXISTS scan_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    waybill_number TEXT NOT NULL DEFAULT '',
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

-- terminated_waybills
CREATE TABLE IF NOT EXISTS terminated_waybills (
    waybill_number TEXT PRIMARY KEY,
    terminated_at TEXT NOT NULL,
    user_id INTEGER NOT NULL
);

-- In the bo_items table definition
CREATE TABLE IF NOT EXISTS bo_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    go_item TEXT NOT NULL,
    oracle TEXT,
    item_number TEXT,
    discrete_job TEXT,
    part_number TEXT NOT NULL,
    qty_req INTEGER NOT NULL,
    qty_fulfilled INTEGER NOT NULL DEFAULT 0,
    amo_stock_qty INTEGER NOT NULL DEFAULT 0,
    kanban_stock_qty INTEGER NOT NULL DEFAULT 0,
    surplus_stock_qty INTEGER NOT NULL DEFAULT 0,
    redcon_status INTEGER NOT NULL DEFAULT 99,
    pick_status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    flow_status TEXT,
    last_import_date TEXT NOT NULL,
    UNIQUE(go_item, part_number)
);