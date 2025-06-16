# login.py

"""
Handles user authentication for Receiving & Shipping Tracker.
Provides a small login window and helper functions to validate a
user against the SQLite database. Successful logins create a
new entry in the ``scan_sessions`` table.
"""

from __future__ import annotations

import logging

from typing import Optional, Tuple

import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.data_manager import DataManager

logger = logging.getLogger(__name__)

#DB_PATH = "receiving_tracker.db"

def authenticate_user(
    username: str,
    password: str,
    db_path: str = DB_PATH,
) -> Optional[Tuple[int, str, str]]:
    """Validate ``username``/``password`` using :class:`DataManager`."""
    return DataManager(db_path).authenticate_user(username, password)


def create_session(user_id: int, db_path: str = DB_PATH, waybill: str = "") -> int:
    """Create a scan session using :class:`DataManager`."""
    return DataManager(db_path).create_session(user_id, waybill)


def end_session(session_id: int, db_path: str = DB_PATH) -> None:
    """Finish ``session_id`` using :class:`DataManager`."""
    DataManager(db_path).end_session(session_id)


class LoginWindow(ctk.CTk):
    """
    Simple login window returning the authenticated user information.
    The result tuple is (user_id, username, role).
    """

    def __init__(self, db_path: str = DB_PATH):
        super().__init__()
        self.db_path = db_path
        self.title("Receiving & Shipping Tracker - Login")
        self.geometry("300x250")
        ctk.set_appearance_mode("light")

        self.username_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.result: Optional[Tuple[int, str, str]] = None

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
            logger.warning("Login failed for user %s", username)
            messagebox.showerror("Login failed", "Invalid username or password")
            return

        logger.info("User %s authenticated", username)

        # store result: (user_id, username, role)
        self.result = (user[0], user[1], user[2])
        self.destroy()

def prompt_login(db_path: str = DB_PATH) -> Optional[Tuple[int, str, str]]:
    """
    Display the login window and return (user_id, username, role)
    on success, otherwise None.
    """

    window = LoginWindow(db_path)
    window.mainloop()
    return window.result
