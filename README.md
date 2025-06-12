# RECEIVING SHIPPING TRACKER

A barcode-based inventory receiving application for AMO/KANBAN operations.

## 💾 Setup

### 1. Install Python 3.x

### 2. Create the database

```bash
python database/init_db.py

receiving_shipping_tracker/
├── data/                  # Excel files for testing
├── database/
│   ├── schema.sql         # SQL schema
│   └── init_db.py         # Creates SQLite DB
├── src/
│   ├── main.py            # Entry point
│   ├── logic/             # Business logic
│   └── ui/                # UI layer (ex: Streamlit)
├── .gitignore
└── README.md
