"""Admin interface for Receiving & Shipping Tracker."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from src.logic import waybill_import

from src.config import DB_PATH
from src.data_manager import DataManager

#DB_PATH = "receiving_tracker.db"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def import_waybill_file(filepath: str, db_path: str = DB_PATH) -> int:
    """Import ``filepath`` using :func:`waybill_import.import_waybill`."""
    return waybill_import.import_waybill(filepath, db_path)


def get_users(db_path: str = DB_PATH) -> List[tuple[int, str, str]]:
    """Return all users sorted by username."""
    return DataManager(db_path).get_users()


def create_user(
    username: str,
    password: str,
    role: str,
    db_path: str = DB_PATH,
) -> None:
    """Create a new user with ``username`` and ``role``."""
    DataManager(db_path).create_user(username, password, role)


def update_user(
    user_id: int,
    username: str,
    role: str,
    password: Optional[str] = None,
    db_path: str = DB_PATH,
) -> None:
    """Update ``username``/``role`` and optionally ``password`` for ``user_id``."""
    DataManager(db_path).update_user(user_id, username, role, password)


def delete_user(user_id: int, db_path: str = DB_PATH) -> None:
    """Delete user with ``user_id``."""
    DataManager(db_path).delete_user(user_id)


def query_scan_summary(
    user_id: Optional[int] = None,
    date: Optional[str] = None,
    waybill: Optional[str] = None,
    db_path: str = DB_PATH,
) -> List[tuple]:
    """Return scan summary rows filtered by ``user_id``, ``date`` and ``waybill``."""
    dm = DataManager(db_path)
    return dm.query_scan_summary(user_id, date, waybill)


def export_summary_to_csv(rows: Iterable[tuple], filepath: str) -> None:
    """Write ``rows`` to ``filepath`` as CSV."""
    headers = [
        "waybill_number",
        "user",
        "part_number",
        "total_scanned",
        "expected_qty",
        "remaining_qty",
        "allocated_to",
        "reception_date",
    ]
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# UI classes
# ---------------------------------------------------------------------------

class AdminWindow(ctk.CTk):
    def __init__(self, db_path: str = DB_PATH):
        super().__init__()
        self.db_path = db_path
        self.title("Admin Interface")
        self.geometry("900x600")
        ctk.set_appearance_mode("light")

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_upload = tabs.add("Waybill Upload")
        self.tab_users = tabs.add("User Management")
        self.tab_summary = tabs.add("Scan Summaries")

        self._build_upload_tab()
        self._build_user_tab()
        self._build_summary_tab()

    # ---------------------------- Waybill Upload ----------------------------
    def _build_upload_tab(self) -> None:
        btn = ctk.CTkButton(
            self.tab_upload, text="Import Waybill", command=self._choose_waybill
        )
        btn.pack(pady=20)

    def _choose_waybill(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Waybill", filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not path:
            return
        try:
            inserted = import_waybill_file(path, self.db_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Import failed", str(exc))
            return
        messagebox.showinfo(
            "Waybill imported", f"{inserted} lines inserted from {Path(path).name}"
        )

    # ---------------------------- User Management ---------------------------
    def _build_user_tab(self) -> None:
        self.users: List[tuple[int, str, str]] = []

        self.user_list = ctk.CTkFrame(self.tab_users)
        self.user_list.pack(side="left", fill="y", padx=10, pady=10)
        self.listbox = ctk.CTkScrollableFrame(self.user_list, width=200)
        self.listbox.pack(fill="both", expand=True)

        self.user_buttons = []
        self._refresh_user_list()

        form = ctk.CTkFrame(self.tab_users)
        form.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.username_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.role_var = ctk.StringVar(value="SHIPPER")

        ctk.CTkLabel(form, text="Username:").grid(row=0, column=0, sticky="e")
        ctk.CTkEntry(form, textvariable=self.username_var).grid(
            row=0, column=1, padx=5, pady=5
        )

        ctk.CTkLabel(form, text="Password:").grid(row=1, column=0, sticky="e")
        ctk.CTkEntry(form, textvariable=self.password_var, show="*").grid(
            row=1, column=1, padx=5, pady=5
        )

        ctk.CTkLabel(form, text="Role:").grid(row=2, column=0, sticky="e")
        ctk.CTkOptionMenu(
            form,
            variable=self.role_var,
            values=["ADMIN", "SHIPPER"],
        ).grid(row=2, column=1, padx=5, pady=5, sticky="w")


        btn_frame = ctk.CTkFrame(form)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Add", command=self._add_user).pack(
            side="left", padx=5
        )
        ctk.CTkButton(btn_frame, text="Update", command=self._update_user).pack(
            side="left", padx=5
        )
        ctk.CTkButton(btn_frame, text="Delete", command=self._delete_user).pack(
            side="left", padx=5
        )

    def _refresh_user_list(self) -> None:
        for widget in self.listbox.winfo_children():
            widget.destroy()
        self.users = get_users(self.db_path)
        for idx, (_, username, role) in enumerate(self.users):
            btn = ctk.CTkButton(
                self.listbox,
                text=f"{username} ({role})",
                width=180,
                command=lambda i=idx: self._select_user(i),
            )
            btn.pack(fill="x", pady=2)
            self.user_buttons.append(btn)

    def _select_user(self, index: int) -> None:
        user_id, username, role = self.users[index]
        self.selected_user = user_id
        self.username_var.set(username)
        self.role_var.set(role)
        self.password_var.set("")

    def _add_user(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        role = self.role_var.get()
        if not username or not password:
            messagebox.showwarning("Missing data", "Username and password required")
            return
        try:
            create_user(username, password, role, self.db_path)
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists")
            return
        self.username_var.set("")
        self.password_var.set("")
        self._refresh_user_list()

    def _update_user(self) -> None:
        if not hasattr(self, "selected_user"):
            messagebox.showinfo("Select user", "Please select a user to update")
            return
        username = self.username_var.get().strip()
        role = self.role_var.get()
        password = self.password_var.get().strip() or None
        update_user(self.selected_user, username, role, password, self.db_path)
        self.password_var.set("")
        self._refresh_user_list()

    def _delete_user(self) -> None:
        if not hasattr(self, "selected_user"):
            messagebox.showinfo("Select user", "Please select a user to delete")
            return
        if messagebox.askyesno("Confirm", "Delete selected user?"):
            delete_user(self.selected_user, self.db_path)
            self.username_var.set("")
            self.password_var.set("")
            self._refresh_user_list()

    # --------------------------- Scan Summaries -----------------------------
    def _build_summary_tab(self) -> None:
        filter_frame = ctk.CTkFrame(self.tab_summary)
        filter_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(filter_frame, text="User:").pack(side="left")
        self.summary_user_var = ctk.StringVar(value="All")
        user_names = ["All"] + [u[1] for u in get_users(self.db_path)]
        self.user_menu = ctk.CTkOptionMenu(
            filter_frame, variable=self.summary_user_var, values=user_names
        )
        self.user_menu.pack(side="left", padx=5)

        ctk.CTkLabel(filter_frame, text="Date:").pack(side="left", padx=(20, 0))
        self.date_var = ctk.StringVar()
        ctk.CTkEntry(filter_frame, textvariable=self.date_var, width=120).pack(
            side="left", padx=5
        )

        ctk.CTkLabel(filter_frame, text="Waybill:").pack(side="left", padx=(20, 0))
        self.waybill_var = ctk.StringVar()
        ctk.CTkEntry(filter_frame, textvariable=self.waybill_var, width=120).pack(
            side="left", padx=5
        )

        ctk.CTkButton(filter_frame, text="Load", command=self._load_summary).pack(
            side="left", padx=10
        )
        ctk.CTkButton(
            filter_frame, text="Export CSV", command=self._export_summary
        ).pack(side="left")

        columns = [
            "Waybill",
            "User",
            "Part",
            "Scanned",
            "Expected",
            "Remaining",
            "Allocated",
            "Date",
        ]
        self.tree = ttk.Treeview(
            self.tab_summary, columns=columns, show="headings", height=15
        )
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.summary_rows: List[tuple] = []

    def _load_summary(self) -> None:
        user_name = self.summary_user_var.get()
        user_id = None
        if user_name != "All":
            for uid, name, _ in get_users(self.db_path):
                if name == user_name:
                    user_id = uid
                    break
        date = self.date_var.get().strip() or None
        waybill = self.waybill_var.get().strip() or None

        rows = query_scan_summary(user_id, date, waybill, self.db_path)
        self.summary_rows = rows
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            self.tree.insert("", "end", values=row)

    def _export_summary(self) -> None:
        if not self.summary_rows:
            messagebox.showinfo("No data", "Load summary first")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        export_summary_to_csv(self.summary_rows, path)
        messagebox.showinfo("Exported", f"Summary exported to {Path(path).name}")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def start_admin_interface(db_path: str = DB_PATH) -> None:
    """Launch the admin interface."""
    app = AdminWindow(db_path)
    app.mainloop()
