# scanner_interface.py
"""
User interface logic for the SHIPPER role.
Allows scanning parts against an active Waybill and updates database.
"""

# TODO: Create interface (ex: tkinter/customtkinter) to:
#   - Select a Waybill from list of active waybills in DB
#   - Show list of PART_NUMBERs with their remaining quantities
#   - Display inventory type (AMO/KANBAN) and progress bar (color gradient)
#   - Allow quantity input (default = 1, reset after each scan)
#   - Continuously listen for scanner input (keyboard emulation)

# TODO: Validate each scanned part:
#   - Match against `waybill_lines`
#   - Apply logic from spec (prioritize AMO, block if over qty, etc.)
#   - Record each scan in `scan_events`

# TODO: Auto-complete a Waybill when all QTYs are scanned (or allow manual button)
# TODO: Provide audio or visual feedback on success/error

# TODO: Optional features:
#   - Display part info after scan
#   - Search for part manually
#   - Highlight invalid scans

# Dependencies (to be used by Codex):
# import sqlite3
# import tkinter
# from datetime import datetime

# def start_shipper_interface(user_id: int):
#     ... (Codex to implement)
#     pass
