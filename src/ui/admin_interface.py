# admin_interface.py
"""
Admin interface for Receiving & Shipping Tracker.
Allows uploading waybills, managing users, and viewing scan summaries.
"""

# TODO: Build interface with tkinter/customtkinter
# TODO: Show dashboard with the following sections:
#   - 📥 Upload new Waybill Excel file (calls waybill_import.import_waybill)
#   - 👤 Manage users (add, delete, change password, assign role)
#   - 📊 View scan summaries (by date, user, waybill)
#   - 💾 Export scan summary to CSV (from `scan_summary` table)

# TODO: For waybill upload:
#   - Validate file format (Excel, proper headers)
#   - Show confirmation after successful import

# TODO: For user management:
#   - Create new user with role selection (SHIPPER or ADMIN)
#   - Store password hashed (SHA-256)
#   - Show list of users with edit/delete actions

# TODO: For viewing summaries:
#   - Select filters (user, date range, waybill)
#   - Display results in table
#   - Allow export as CSV

# Optional features:
# - Display session activity log
# - Audit trail for modifications

# Dependencies:
# import sqlite3
# import tkinter
# import hashlib
# import pandas as pd

# def start_admin_interface(user_id: int):
#     ... (to be implemented)
#     pass