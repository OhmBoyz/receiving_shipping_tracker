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


## Workflow

Scanning progress is recorded continuously in the `scan_events` table as each barcode is processed. A summary row in `scan_summary` is only written when the user finishes a waybill or ends the session via the cleanup routine. If the application is terminated unexpectedly, only the `scan_events` entries remain and the summary may be missing.


## Importing Part Identifiers

Part identifiers map UPC barcodes to internal part numbers. They also allow the
system to apply a default quantity and store a short description for each UPC.

Administrators can load these mappings from a CSV file:

1. Open the **Admin** interface and switch to the **Waybill Upload** tab.
2. Click the **Import Part Identifiers** button and select your CSV file.
3. The file must contain the following column headers:
   - `part_number`
   - `upc_code`
   - `qty`
   - `description`