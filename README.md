# RECEIVING SHIPPING TRACKER

A barcode-based inventory receiving application for AMO/KANBAN operations.

## 💾 Setup

### 1. Install Python 3.x

## To set up the environment
pip install -r requirements.txt

### 2. To create the database if not existing

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

### Logs

Runtime logs are written to `tracker.log` in the project root. This file is
created automatically when the application starts.
