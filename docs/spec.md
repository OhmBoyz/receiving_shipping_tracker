RECEIVING & SHIPPING TRACKER
=============================

## 1. GOAL
A program that a **shipper** can use to **scan incoming stock** and allocate it correctly into inventory (AMO / KANBAN / BO).

## 2. CONTEXT
- Daily, material arrives (breakers, connectors, etc.).
- A "Waybill" report (from Oracle) lists the expected parts.
- Shipments arrive via **TST** or **PURO**.
- Only **one person** does the receiving at a time.
- Sometimes, **partial shipments** or **missing items** occur.
- The scanner behaves like a **USB keyboard** (Code128, UPC).
- UPCs are resolved via an **Access DB** (`PART_IDENTIFIERS`) or a CSV fallback.

## 3. USER ROLES

### ADMIN
- Can do everything a shipper can do
- Add / modify / remove users
- Upload or re-upload Waybills
- Edit scans
- Consult scan summaries (by session, user, date, waybill)

### SHIPPER
- Select a palette (Waybill number)
- Scan or manually enter part numbers
- Enter quantity before each scan
- View real-time progress: scanned qty, remaining qty
- Visual feedback: inventory type, scan validity, color cues
- Mark palette as finished manually or auto-complete

## 4. PROJECT PHASES
1. **Database structure** (status: not started)
2. **App interface and scanning logic** (status: not started)
3. **BO integration and automation** (status: not started)

## 5. DATABASE STRUCTURE (UPDATED)

### Suggested Tables
- **users**: user_id, username, password_hash, role
- **part_identifiers**: part_number, upc_code, alt_code, description
- **waybill_lines**: id, waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date
- **scan_sessions**: session_id, user_id, start_time, end_time, waybill_number
- **scan_events**: id, session_id, part_number, scanned_qty, timestamp, raw_scan
- **scan_summary**: id, session_id, part_number, total_scanned, expected_qty, remaining_qty, allocated_to, reception_date, user_id

These tables together:
- allow tracking of partial receptions across days,
- support detailed user-based logging,
- simplify reporting and export generation,
- eliminate the need for `waybills_active`, `waybills_finished`, and `palette_active`, which are now fully handled by `waybill_lines` + scan logic.

## 6. SCANNER & PART IDENTIFICATION
- Most barcodes are **Code128** (return part number directly)
- Some are **UPC**, resolved to part number via Access DB (`PART_IDENTIFIERS`) or fallback CSV
- Scans must be matched against the current active palette lines

## 7. WAYBILL FILE SPECIFICATION
- **Excel format**, structured as follows:
  - Row 1: ignored
  - Row 2: headers
  - Row 3+: data begins

| Column | Name                     | Notes                             |
|--------|--------------------------|-----------------------------------|
| A      | SHIPMENT_NUM            | Ignored                           |
| B      | ITEM                    | Part number                       |
| C      | DESCRIPTION             | Part description                  |
| D      | SHP QTY                 | Quantity expected                 |
| F      | IR_NUM                  | Ignored                           |
| G-H    | Oracle Info             | Ignored                           |
| I      | ORG                     | Origin site code                  |
| J      | DEST_IO                 | Must be our site code             |
| K      | SUBINV                  | Inventory type (DRV-AMO, DRV-RM)  |
| L      | LOCATOR                 | AMO or KB location code           |
| M-N    | UOM / SHIP_METHOD       | Ignored                           |
| O      | WAYBILL                 | Treated as "palette ID"           |
| P      | ITEM_COSTS              | Unit cost                         |
| Q      | SHIP METHOD             | TST / PURO                        |
| R-S-T  | Other                   | Ignored                           |

## 8. INVENTORY LOGIC

### Mapping SUBINV → Inventory
- `DRV-AMO` → AMO
- `DRV-RM` → KANBAN

### Rules:
- A part can be present in **both** AMO and KANBAN (must show how much in each)
- Unscanned lines must always be clearly visible
- Invalid scans (not in Waybill) must be flagged
- ✅ A part number can be scanned multiple times (accumulated over time)
- 🚫 If scanning would exceed expected QTY, the scan is blocked
- ⚠️ Clear **visual and/or audio warning** is required when blocking over-scans
- ✅ Default quantity = 1 if no value is specified
- 🔁 Quantity input resets to 1 automatically after each scan
- 🤖 If the same part number exists on multiple lines (e.g., AMO and KANBAN), the program automatically allocates scans **prioritizing AMO first**, then KANBAN, based on remaining quantity. No user intervention required.

## 9. UI REQUIREMENTS

### For SHIPPER
- Minimal clicks
- Manual part number input allowed
- Quantity input before scanning (default = 1, resets after each scan)
- Display part info after scan
- Clear display of what goes where (AMO/KANBAN/BO)
- Warnings for invalid scans
- Mark palette done manually or automatically
- ✅ Display a **progress bar per part number**, ideally using **color gradient**
  - Ex: from red (0%) to green (100%)
  - ✅ Compatible with distant screen viewing

### For ADMIN
- Upload Waybill files
- View scan logs
- Manage users
- ✅ Access and export scan summaries per session, user, or waybill (from `scan_summary`)

## 10. AUTHENTICATION
- Users must **log in** with a **username and password**.
- Each user session is tracked and recorded.
- The session will associate each scan to the logged-in user.

## 11. BO REPORT (TO BE IMPLEMENTED LATER)

### File Spec:
- Excel file, with data starting at **row 2**
- Columns:

| Column | Name                  | Notes                                |
|--------|-----------------------|--------------------------------------|
| A      | GO-ITEM               | GO number + item (format: ????######-###?#) |
| B      | ORACLE                | 7-digit number                       |
| C      | PART NUMBER           | Part to be picked                    |
| D      | QTY REQ               | Qty needed for BO                    |
| E-G    | AMO, SURPLUS, KB      | Qty expected in inventory            |
| H      | FLOW STATUS           | AWAITING_SHIPPING or BOOKED          |
| I      | REDCON STATUS         | From 1 (urgent) to 5 (not urgent)    |

### BO Integration Goals:
- On receiving, immediately allocate scanned parts to BO if match found
- Show GO-ITEM if relevant
- Update BO report at end of receiving session

## 12. NEXT STEPS
Let’s clarify step-by-step the following missing pieces:
1. ✅ Authentication with login/password is required. User sessions must be tracked to associate actions with each user.
2. ✅ Parts can be scanned multiple times as long as total does not exceed expected quantity. If exceeded, block scan and show visual/audio alert.
3. ✅ Quantity defaults to 1. After each scan, it resets to 1. A numeric input option is preferred for flexibility, but the system must validate numeric input and block invalid values.
4. ✅ When a part number appears on multiple lines (AMO + KANBAN), the system auto-allocates scans to AMO first, then KANBAN. The shipper does not need to choose.
5. ✅ Scan summary should be saved in the DB (`scan_summary`) and exportable (e.g. CSV) at the end of each session. ADMIN can consult and re-export any session later.