"""Admin interface for Receiving & Shipping Tracker."""

from __future__ import annotations

import logging

import csv
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from src.logic import waybill_import, part_identifier_import

from src.config import DB_PATH, APPEARANCE_MODE
from src.data_manager import DataManager

logger = logging.getLogger(__name__)

# DB_PATH = "receiving_tracker.db"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def import_waybill_file(filepath: str, db_path: str = DB_PATH) -> int:
    """Import ``filepath`` using :func:`waybill_import.import_waybill`."""
    return waybill_import.import_waybill(filepath, db_path)


def import_part_identifier_file(filepath: str, db_path: str = DB_PATH) -> int:
    """Import ``filepath`` using :func:`part_identifier_import.import_part_identifiers`."""
    return part_identifier_import.import_part_identifiers(filepath, db_path)


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
        ctk.set_appearance_mode(APPEARANCE_MODE)

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_upload = tabs.add("Waybill Upload")
        self.tab_users = tabs.add("User Management")
        self.tab_summary = tabs.add("Scan Summaries")
        self.tab_waybill = tabs.add("Waybill Manager")
        self.tab_db = tabs.add("Database Viewer")

        self._build_upload_tab()
        self._build_user_tab()
        self._build_summary_tab()
        self._build_waybill_tab()
        self._build_db_tab()

    # ---------------------------- Waybill Upload ----------------------------
    def _build_upload_tab(self) -> None:
        btn = ctk.CTkButton(
            self.tab_upload, text="Import Waybill", command=self._choose_waybill
        )
        btn.pack(pady=20)

        id_btn = ctk.CTkButton(
            self.tab_upload,
            text="Import Part Identifiers",
            command=self._choose_part_identifiers,
        )
        id_btn.pack(pady=(0, 20))

    def _choose_waybill(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Waybill", filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not path:
            return
        try:
            inserted = import_waybill_file(path, self.db_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Waybill import failed: %s", path)
            messagebox.showerror("Import failed", str(exc))
            return
        logger.info("Imported %s with %d lines", path, inserted)
        messagebox.showinfo(
            "Waybill imported", f"{inserted} lines inserted from {Path(path).name}"
        )

    def _choose_part_identifiers(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Part Identifier CSV", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        try:
            inserted = import_part_identifier_file(path, self.db_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Part identifier import failed: %s", path)
            messagebox.showerror("Import failed", str(exc))
            return
        logger.info("Imported part identifiers %s with %d rows", path, inserted)
        messagebox.showinfo(
            "Import complete",
            f"{inserted} records inserted from {Path(path).name}",
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

    # --------------------------- Waybill Manager ---------------------------
    def _build_waybill_tab(self) -> None:
        self.dm = DataManager(self.db_path)
        self.wb_list = ctk.CTkScrollableFrame(self.tab_waybill, width=200)
        self.wb_list.pack(side="left", fill="y", padx=10, pady=10)
        self.wb_buttons: dict[str, ctk.CTkButton] = {}

        self.wb_actions = ctk.CTkFrame(self.tab_waybill)
        self.wb_actions.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        toolbar = ctk.CTkFrame(self.wb_actions)
        toolbar.pack(fill="x")

        self.wb_term_btn = ctk.CTkButton(
            toolbar,
            text="Terminate",
            command=self._terminate_selected_waybill,
            state="disabled",
        )
        self.wb_term_btn.pack(side="left", padx=5)

        self.wb_table = ctk.CTkScrollableFrame(self.wb_actions)
        self.wb_table.pack(fill="both", expand=True, pady=5)
        self._wb_row_widgets: dict[int, tuple[ctk.StringVar, ctk.CTkLabel, str]] = {}

        self.selected_waybill: Optional[str] = None
        self._refresh_waybill_list()

    def _refresh_waybill_list(self) -> None:
        for widget in self.wb_list.winfo_children():
            widget.destroy()
        self.wb_buttons = {}
        progress = self.dm.get_waybill_progress()
        for wb, total, remaining in progress:
            text = f"{wb} ({total-remaining}/{total})"
            btn = ctk.CTkButton(
                self.wb_list,
                text=text,
                width=180,
                command=lambda n=wb: self._select_waybill(n),
            )
            btn.pack(fill="x", pady=2)
            self.wb_buttons[wb] = btn

    def _select_waybill(self, wb: str) -> None:
        self.selected_waybill = wb
        for btn in self.wb_buttons.values():
            btn.configure(fg_color=None, text_color=None)
        if wb in self.wb_buttons:
            self.wb_buttons[wb].configure(fg_color="#1f6aa5", text_color="white")
        self.wb_term_btn.configure(state="normal")
        self._load_waybill_table(wb)

    def _edit_selected_waybill(self) -> None:
        if not self.selected_waybill:
            return
        self._edit_waybill(self.selected_waybill)

    def _terminate_selected_waybill(self) -> None:
        if not self.selected_waybill:
            return
        self._terminate_waybill(self.selected_waybill)

    def _edit_waybill(self, waybill: str) -> None:
        lines = self.dm.get_waybill_lines(waybill)
        if not lines:
            return
        scans = self.dm.fetch_scans(waybill)

        part_groups: Dict[str, List[tuple]] = {}
        for ln in lines:
            part_groups.setdefault(ln[1], []).append(ln)

        allocated: Dict[int, int] = {}
        for part, lns in part_groups.items():
            lns.sort(key=lambda l: 0 if "AMO" in l[3] else 1)
            remaining = scans.get(part, 0)
            for ln in lns:
                alloc = min(ln[2], remaining)
                allocated[ln[0]] = alloc
                remaining -= alloc

        win = ctk.CTkToplevel(self)
        vars: List[ctk.StringVar] = []
        for i, line in enumerate(lines):
            alloc = allocated.get(line[0], 0)
            remaining = line[2] - alloc
            ctk.CTkLabel(win, text=f"{line[1]} {line[3]}").grid(row=i, column=0, sticky="e")
            var = ctk.StringVar(value=str(remaining))
            vars.append(var)
            ctk.CTkEntry(win, textvariable=var, width=80).grid(row=i, column=1, padx=5, pady=2)

        def save() -> None:
            conn = sqlite3.connect(self.db_path)
            conn.execute("BEGIN")
            for ln, var in zip(lines, vars):
                alloc_scanned = allocated.get(ln[0], 0)
                try:
                    new_remaining = int(var.get())
                except ValueError:
                    messagebox.showwarning("Invalid value", "Enter a numeric quantity")
                    new_remaining = ln[2] - alloc_scanned
                if new_remaining < 0:
                    messagebox.showwarning("Invalid value", "Quantity cannot be negative")
                    new_remaining = 0
                new_total = alloc_scanned + max(new_remaining, 0)
                self.dm.update_row("waybill_lines", ln[0], {"qty_total": new_total}, conn)
            conn.commit()
            conn.close()
            win.destroy()
            logger.info("Waybill %s lines edited", waybill)
            self._refresh_waybill_list()

        def cancel() -> None:
            win.destroy()

        btn_frame = ctk.CTkFrame(win)
        btn_frame.grid(row=len(lines), column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Save", command=save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=cancel).pack(side="left", padx=5)

    def _terminate_waybill(self, waybill: str) -> None:
        self.dm.mark_waybill_terminated(waybill, 0)
        logger.info("Waybill %s marked terminated", waybill)
        self._refresh_waybill_list()

    def _load_waybill_table(self, waybill: str) -> None:
        lines = self.dm.get_waybill_lines(waybill)
        scans = self.dm.fetch_scans(waybill)

        part_groups: Dict[str, List[tuple]] = {}
        for ln in lines:
            part_groups.setdefault(ln[1], []).append(ln)

        allocated: Dict[int, int] = {}
        for part, lns in part_groups.items():
            lns.sort(key=lambda l: 0 if "AMO" in l[3] else 1)
            remaining = scans.get(part, 0)
            for ln in lns:
                alloc = min(ln[2], remaining)
                allocated[ln[0]] = alloc
                remaining -= alloc
        for widget in self.wb_table.winfo_children():
            widget.destroy()
        header = ctk.CTkFrame(self.wb_table)
        header.pack(fill="x")
        for text, width in [
            ("Part", 200),
            ("Remaining", 80),
            ("Remaining", 80),
        ]:
            ctk.CTkLabel(header, text=text, width=width).pack(side="left")

        self._wb_row_widgets.clear()
        for rowid, part, qty_total, _ in lines:
            alloc = allocated.get(rowid, 0)
            remaining = qty_total - alloc
            frame = ctk.CTkFrame(self.wb_table)
            frame.pack(fill="x", pady=1)
            ctk.CTkLabel(frame, text=part, width=200, anchor="w").pack(side="left")
            var = ctk.StringVar(value=str(remaining))
            entry = ctk.CTkEntry(frame, textvariable=var, width=80)
            entry.pack(side="left", padx=5)
            lbl = ctk.CTkLabel(frame, text=str(remaining), width=80)
            lbl.pack(side="left")
            entry.bind(
                "<Return>",
                lambda e, rid=rowid, p=part, v=var, lb=lbl: self._update_qty(rid, p, v, lb),
            )
            entry.bind(
                "<FocusOut>",
                lambda e, rid=rowid, p=part, v=var, lb=lbl: self._update_qty(rid, p, v, lb),
            )
            self._wb_row_widgets[rowid] = (var, lbl, part)

    def _update_qty(
        self, rowid: int, part: str, var: ctk.StringVar, label: ctk.CTkLabel
    ) -> None:
        try:
            new_remaining = int(var.get())
        except ValueError:
            messagebox.showwarning("Invalid value", "Enter a numeric quantity")
            return
        if new_remaining < 0:
            messagebox.showwarning("Invalid value", "Quantity cannot be negative")
            new_remaining = 0
        scans = self.dm.fetch_scans(self.selected_waybill or "")
        scanned = scans.get(part, 0)
        new_total = scanned + max(new_remaining, 0)
        self.dm.update_row("waybill_lines", rowid, {"qty_total": new_total})
        label.configure(text=str(new_remaining))
        self._refresh_waybill_list()

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

    # --------------------------- Database Viewer ---------------------------
    def _build_db_tab(self) -> None:
        self.dm = DataManager(self.db_path)
        self.table_list = ctk.CTkFrame(self.tab_db)
        self.table_list.pack(side="left", fill="y", padx=10, pady=10)
        self.table_buttons: List[ctk.CTkButton] = []
        self.table_frame = ctk.CTkFrame(self.tab_db)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        toolbar = ctk.CTkFrame(self.table_frame)
        toolbar.pack(fill="x")
        self.add_btn = ctk.CTkButton(
            toolbar, text="Add", command=self._add_row, state="disabled"
        )
        self.add_btn.pack(side="left", padx=2)
        self.edit_btn = ctk.CTkButton(
            toolbar, text="Edit", command=self._edit_selected_row, state="disabled"
        )
        self.edit_btn.pack(side="left", padx=2)
        self.del_btn = ctk.CTkButton(
            toolbar, text="Delete", command=self._delete_selected_row, state="disabled"
        )
        self.del_btn.pack(side="left", padx=2)

        self.table_tree = ttk.Treeview(self.table_frame, show="headings")
        self.table_tree.pack(fill="both", expand=True, pady=(5, 0))
        self.table_tree.bind("<<TreeviewSelect>>", self._on_row_select)

        self.selected_rowid: Optional[int] = None

        self._refresh_table_list()

    def _refresh_table_list(self) -> None:
        for widget in self.table_list.winfo_children():
            widget.destroy()
        tables = self.dm.fetch_table_names()
        for name in tables:
            btn = ctk.CTkButton(
                self.table_list,
                text=name,
                width=160,
                command=lambda n=name: self._load_table(n),
            )
            btn.pack(fill="x", pady=2)
            self.table_buttons.append(btn)

    def _load_table(self, name: str) -> None:
        self.current_table = name
        self.selected_rowid = None
        self.edit_btn.configure(state="disabled")
        self.del_btn.configure(state="disabled")
        add_state = "normal" if name == "part_identifiers" else "disabled"
        self.add_btn.configure(state=add_state)

        for item in self.table_tree.get_children():
            self.table_tree.delete(item)

        cols, rows = self.dm.fetch_rows(name)
        self.table_tree.configure(columns=cols)
        for col in cols:
            self.table_tree.heading(col, text=col)
            self.table_tree.column(col, width=120, anchor="center")

        for row in rows:
            self.table_tree.insert("", "end", values=row)

    def _edit_row(self, pk: int) -> None:
        cols, rows = self.dm.fetch_rows(self.current_table)
        row_data = next((r for r in rows if r[0] == pk), None)
        if row_data is None:
            return
        data_cols = cols[1:]
        values = row_data[1:]
        win = ctk.CTkToplevel(self)
        win.title("Edit Row")
        vars: List[ctk.StringVar] = []
        for i, (col, val) in enumerate(zip(data_cols, values)):
            ctk.CTkLabel(win, text=col).grid(row=i, column=0, sticky="e")
            var = ctk.StringVar(value=str(val))
            vars.append(var)
            ctk.CTkEntry(win, textvariable=var).grid(row=i, column=1, padx=5, pady=2)

        def save() -> None:
            conn = sqlite3.connect(self.db_path)
            conn.execute("BEGIN")
            data = {col: var.get() for col, var in zip(data_cols, vars)}
            self.dm.update_row(self.current_table, pk, data, conn)
            if messagebox.askyesno("Confirm", "Save changes?"):
                conn.commit()
            else:
                conn.rollback()
            conn.close()
            win.destroy()
            self._load_table(self.current_table)

        def cancel() -> None:
            win.destroy()

        btn_frame = ctk.CTkFrame(win)
        btn_frame.grid(row=len(data_cols), column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Save", command=save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=cancel).pack(
            side="left", padx=5
        )

    def _delete_row(self, pk: int) -> None:
        if not messagebox.askyesno("Confirm", "Delete selected row?"):
            return
        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN")
        self.dm.delete_row(self.current_table, pk, conn)
        if messagebox.askyesno("Confirm", "Commit deletion?"):
            conn.commit()
        else:
            conn.rollback()
        conn.close()
        self._load_table(self.current_table)

    # --------------------------- Table callbacks ---------------------------
    def _on_row_select(self, event: object | None = None) -> None:
        selection = self.table_tree.selection()
        if not selection:
            self.selected_rowid = None
            self.edit_btn.configure(state="disabled")
            self.del_btn.configure(state="disabled")
            return
        item = selection[0]
        values = self.table_tree.item(item, "values")
        if not values:
            return
        self.selected_rowid = int(values[0])
        self.edit_btn.configure(state="normal")
        self.del_btn.configure(state="normal")

    def _add_row(self) -> None:
        if self.current_table != "part_identifiers":
            return

        win = ctk.CTkToplevel(self)
        win.title("Add Part Identifier")
        fields = ["part_number", "upc_code", "qty", "description"]
        vars: List[ctk.StringVar] = []
        for i, field in enumerate(fields):
            ctk.CTkLabel(win, text=field).grid(row=i, column=0, sticky="e")
            var = ctk.StringVar()
            vars.append(var)
            ctk.CTkEntry(win, textvariable=var).grid(row=i, column=1, padx=5, pady=2)

        def save() -> None:
            part, upc, qty, desc = [v.get().strip() for v in vars]
            if not part:
                messagebox.showwarning("Missing data", "part_number required")
                return
            try:
                qty_int = int(qty) if qty else 0
            except ValueError:
                messagebox.showwarning("Invalid", "qty must be integer")
                return
            self.dm.insert_part_identifiers([(part, upc, qty_int, desc)])
            win.destroy()
            self._load_table(self.current_table)

        def cancel() -> None:
            win.destroy()

        btn_frame = ctk.CTkFrame(win)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Save", command=save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=cancel).pack(
            side="left", padx=5
        )

    def _edit_selected_row(self) -> None:
        if self.selected_rowid is None:
            return
        self._edit_row(self.selected_rowid)

    def _delete_selected_row(self) -> None:
        if self.selected_rowid is None:
            return
        self._delete_row(self.selected_rowid)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def start_admin_interface(db_path: str = DB_PATH) -> None:
    """Launch the admin interface."""
    app = AdminWindow(db_path)
    app.mainloop()
