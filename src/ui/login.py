# login.py

"""
Handles user authentication for Receiving & Shipping Tracker.
Provides a small login window and helper functions to validate a
user against the SQLite database. Successful logins create a
new entry in the ``scan_sessions`` table.
"""

from __future__ import annotations

from typing import Optional, Tuple

import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.data_manager import DataManager

#DB_PATH = "receiving_tracker.db"

def authenticate_user(
    username: str,
    password: str,
    db_path: str = DB_PATH,
) -> Optional[Tuple[int, str, str]]:
    """Validate ``username``/``password`` using :class:`DataManager`."""
    return DataManager(db_path).authenticate_user(username, password)


def create_session(user_id: int, db_path: str = DB_PATH) -> int:
    """Create a scan session using :class:`DataManager`."""
    return DataManager(db_path).create_session(user_id)


def end_session(session_id: int, db_path: str = DB_PATH) -> None:
    """Finish ``session_id`` using :class:`DataManager`."""
    DataManager(db_path).end_session(session_id)


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
    Display the login window and return (session_id, user_id, username, role)
    on success, otherwise None.
    """

    window = LoginWindow(db_path)
    window.mainloop()
    return window.result
