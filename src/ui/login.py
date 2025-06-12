# login.py
"""
Handles user authentication for Receiving & Shipping Tracker
"""

import sqlite3
import hashlib
from datetime import datetime

# TODO: Create a login window using tkinter/customtkinter
# TODO: Prompt for username and password
# TODO: On submit, hash password and validate against DB (`users` table)
#       - Passwords are stored as SHA-256 hashes
# TODO: If login is successful:
#       - Return user_id, username, role
#       - Record new session in `scan_sessions` with start_time
# TODO: If login fails:
#       - Show error message
#       - Allow retry

# Example function (to be completed by Codex)
def authenticate_user(username: str, password: str):
    conn = sqlite3.connect("receiving_tracker.db")
    cursor = conn.cursor()

    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("SELECT user_id, username, role FROM users WHERE username = ? AND password_hash = ?", (username, hashed_pw))
    result = cursor.fetchone()
    conn.close()
    return result

# TODO: Add unit-testable version of authenticate_user
# TODO: Consider lockout after multiple failed attempts
# TODO: (Optional) Audit log for login attempts
