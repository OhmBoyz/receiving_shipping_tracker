# login.py

"""
Handles user authentication for Receiving & Shipping Tracker.
Provides a small login window and helper functions to validate a
user against the SQLite database. Successful logins create a
new entry in the ``scan_sessions`` table.
"""

from __future__ import annotations

import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, Tuple

import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH

#DB_PATH = "receiving_tracker.db"

def authenticate_user(
    username: str,
    password: str,
    db_path: str = DB_PATH
) -> Optional[Tuple[int, str, str]]:
    """
    Validate username and password against the DB.
    Returns a tuple (user_id, username, role) if credentials are correct, otherwise None.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute(
        "SELECT user_id, username, role FROM users WHERE username = ? AND password_hash = ?",
        (username, hashed_pw),
    )
    result = cursor.fetchone()
    conn.close()
    return result  # type: ignore[return-value]


def create_session(user_id: int, db_path: str = DB_PATH) -> int:
    """
    Create a new scan session for user_id and return the session id.
    Always returns an int.
    """
    start_time = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scan_sessions (user_id, waybill_number, start_time) VALUES (?, ?, ?)",
        (user_id, "", start_time),
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Pylance voit lastrowid comme int | None, on s'assure qu'il n'est pas None
    assert session_id is not None, "Failed to create session"
    return session_id


def end_session(session_id: int, db_path: str = DB_PATH) -> None:
    """Mark ``session_id`` as finished by setting its ``end_time``."""
    end_time = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE scan_sessions SET end_time=? WHERE session_id=?",
        (end_time, session_id),
    )
    conn.commit()
    conn.close()


class LoginWindow(ctk.CTk):
    """
    Simple login window returning the authenticated user session info.
    The result tuple is (session_id, user_id, username, role).
    """

    def __init__(self, db_path: str = DB_PATH):
        super().__init__()
        self.db_path = db_path
        self.title("Receiving & Shipping Tracker - Login")
        self.geometry("300x200")
        ctk.set_appearance_mode("light")

        self.username_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.result: Optional[Tuple[int, int, str, str]] = None

        ctk.CTkLabel(self, text="Username:").pack(pady=(20, 5))
        self.username_entry = ctk.CTkEntry(self, textvariable=self.username_var)
        self.username_entry.pack()

        ctk.CTkLabel(self, text="Password:").pack(pady=(10, 5))
        self.password_entry = ctk.CTkEntry(
            self, textvariable=self.password_var, show="*"
        )
        self.password_entry.pack()

        login_btn = ctk.CTkButton(self, text="Login", command=self.attempt_login)
        login_btn.pack(pady=20)

        # Pressing Enter will also attempt login
        self.bind("<Return>", lambda _: self.attempt_login())

    def attempt_login(self) -> None:
        username = self.username_var.get()
        password = self.password_var.get()

        user = authenticate_user(username, password, self.db_path)
        if user is None:
            messagebox.showerror("Login failed", "Invalid username or password")
            return

        session_id = create_session(user[0], self.db_path)
        # store result: (session_id, user_id, username, role)
        self.result = (session_id, user[0], user[1], user[2])
        self.destroy()

def prompt_login(db_path: str = DB_PATH) -> Optional[Tuple[int, int, str, str]]:
    """
    Display the login window and return (session_id, user_id, username, role) on success,
    otherwise None.
    """

    window = LoginWindow(db_path)
    window.mainloop()
    return window.result
