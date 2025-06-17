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
created automatically when the application starts. The log level can be
customized with the `TRACKER_LOG_LEVEL` environment variable. Set it to `DEBUG`
to enable verbose output during troubleshooting.


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

Part lookups read from the `part_identifiers` table. A CSV file is used only if
one is supplied when launching the scanner interface.

## Database Viewer

The **Admin** window now includes a *Database Viewer* tab. It lists all tables
in the SQLite database and lets you inspect and edit their contents. Selecting a
table shows its rows with **Edit** and **Delete** actions. Edits and deletions
are wrapped in a transaction so you can cancel changes before committing.

## Today's Waybills

The shipper interface now lists only the waybills dated today when it starts.
Click **Show All Waybills** to display previous days as well.
