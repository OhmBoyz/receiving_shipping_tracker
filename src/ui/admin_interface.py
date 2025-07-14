"""Admin interface for Receiving & Shipping Tracker."""

from __future__ import annotations

import logging

import csv
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from src.logic import waybill_import, part_identifier_import
from src.config import DB_PATH, APPEARANCE_MODE
from src.data_manager import DataManager
from src.logic.bo_report import import_bo_files
from src.logic import picklist_generator
from src.ui.printer_selection import PrinterSelectDialog

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
        self.tab_fulfillment = tabs.add("BO Fulfillment")
        self.tab_db = tabs.add("Database Viewer")

        self._build_upload_tab()
        self._build_user_tab()
        self._build_summary_tab()
        self._build_waybill_tab()
        self._build_fulfillment_tab()
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

        # --- ADD THIS NEW BUTTON ---
        bo_btn = ctk.CTkButton(
            self.tab_upload,
            text="Import BO Reports (REDCON & BACKLOG)",
            command=self._choose_bo_reports,
        )
        bo_btn.pack(pady=(20, 0))

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
    def _choose_bo_reports(self) -> None:
        """Handles the selection and import of BO report files."""
        messagebox.showinfo("Select BACKLOG File", "First, please select the BACKLOG Excel file.")
        backlog_path = filedialog.askopenfilename(
            title="Select BACKLOG Excel File", filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not backlog_path:
            messagebox.showwarning("Cancelled", "BACKLOG file selection cancelled.")
            return

        messagebox.showinfo("Select REDCON File", "Next, please select the REDCON Excel file.")
        redcon_path = filedialog.askopenfilename(
            title="Select REDCON Excel File", filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not redcon_path:
            messagebox.showwarning("Cancelled", "REDCON file selection cancelled.")
            return

        try:
            created, updated, deleted = import_bo_files(backlog_path, redcon_path, self.db_path)
            messagebox.showinfo(
                "BO Import Complete",
                f"Successfully imported BO data:\n\n"
                f"New Records Created: {created}\n"
                f"Existing Records Updated: {updated}\n"
                f"Stale Records Deleted: {deleted}"
            )
            logger.info(f"BO Import successful: {created} created, {updated} updated, {deleted} deleted.")
        except Exception as exc:
            logger.exception("BO report import failed.")
            messagebox.showerror("BO Import Failed", f"An error occurred: {exc}")

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

        self.edit_mode = False
        self.wb_edit_btn = ctk.CTkButton(
            toolbar,
            text="Edit Waybill",
            command=self._toggle_edit_mode,
            state="disabled",
        )
        self.wb_edit_btn.pack(side="left", padx=5)

        self.wb_term_btn = ctk.CTkButton(
            toolbar,
            text="Terminate",
            command=self._terminate_selected_waybill,
            state="disabled",
        )
        self.wb_term_btn.pack(side="left", padx=5)

        self.wb_table = ctk.CTkScrollableFrame(self.wb_actions)
        self.wb_table.pack(fill="both", expand=True, pady=5)
        self._wb_row_widgets: dict[int, tuple[ctk.StringVar, ctk.CTkLabel, str, ctk.CTkEntry]] = {}

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
            btn.configure(fg_color="grey", text_color="black")
        if wb in self.wb_buttons:
            self.wb_buttons[wb].configure(fg_color="#1f6aa5", text_color="white")
        self.wb_term_btn.configure(state="normal")
        self.wb_edit_btn.configure(state="normal", text="Edit Waybill")
        self.edit_mode = False
        self._load_waybill_table(wb)

    def _edit_selected_waybill(self) -> None:
        if not self.selected_waybill:
            return
        self._edit_waybill(self.selected_waybill)

    def _toggle_edit_mode(self) -> None:
        if not self.selected_waybill:
            return
        self.edit_mode = not self.edit_mode
        state = "normal" if self.edit_mode else "readonly"
        for var, lbl, part, entry in self._wb_row_widgets.values():
            entry.configure(state=state)
        text = "Done Editing" if self.edit_mode else "Edit Waybill"
        self.wb_edit_btn.configure(text=text)

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
            ("Total Qty", 80),
            ("Remaining", 80),
        ]:
            ctk.CTkLabel(header, text=text, width=width).pack(side="left")

        self._wb_row_widgets.clear()
        for rowid, part, qty_total, _, _ in lines:
            alloc = allocated.get(rowid, 0)
            remaining = qty_total - alloc
            frame = ctk.CTkFrame(self.wb_table)
            frame.pack(fill="x", pady=1)
            ctk.CTkLabel(frame, text=part, width=200, anchor="w").pack(side="left")
            qty_lbl = ctk.CTkLabel(frame, text=str(qty_total), width=80)
            qty_lbl.pack(side="left")
            var = ctk.StringVar(value=str(remaining))
            entry = ctk.CTkEntry(frame, textvariable=var, width=80)
            state = "normal" if self.edit_mode else "readonly"
            entry.configure(state=state)
            entry.pack(side="left", padx=5)
            entry.bind(
                "<Return>",
                lambda e, rid=rowid, p=part, v=var, lb=qty_lbl: self._update_qty(rid, p, v, lb),
            )
            entry.bind(
                "<FocusOut>",
                lambda e, rid=rowid, p=part, v=var, lb=qty_lbl: self._update_qty(rid, p, v, lb),
            )
            self._wb_row_widgets[rowid] = (var, qty_lbl, part, entry)

    def _update_qty(
        self, rowid: int, part: str, var: ctk.StringVar, label: ctk.CTkLabel
    ) -> None:
        if not self.edit_mode:
            return
        try:
            new_remaining = int(var.get())
        except ValueError:
            messagebox.showwarning("Invalid value", "Enter a numeric quantity")
            return
        if new_remaining < 0:
            messagebox.showwarning("Invalid value", "Quantity cannot be negative")
            new_remaining = 0
        waybill = self.selected_waybill or ""
        lines = self.dm.get_waybill_lines(waybill)
        scans = self.dm.fetch_scans(waybill)

        part_groups: Dict[str, List[tuple]] = {}
        for ln in lines:
            part_groups.setdefault(ln[1], []).append(ln)

        allocated: Dict[int, int] = {}
        for pnum, lns in part_groups.items():
            lns.sort(key=lambda l: 0 if "AMO" in l[3] else 1)
            remaining = scans.get(pnum, 0)
            for ln in lns:
                alloc = min(ln[2], remaining)
                allocated[ln[0]] = alloc
                remaining -= alloc

        orig_line = next((ln for ln in lines if ln[0] == rowid), None)
        if orig_line is None:
            return
        scanned_for_line = allocated.get(rowid, 0)
        max_remaining = orig_line[2] - scanned_for_line
        if new_remaining > max_remaining:
            new_remaining = max_remaining
        new_total = scanned_for_line + max(new_remaining, 0)
        self.dm.update_row("waybill_lines", rowid, {"qty_total": new_total})
        label.configure(text=str(new_total))
        self._refresh_waybill_list()
        if self.selected_waybill:
            self._load_waybill_table(self.selected_waybill)

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

    def _build_fulfillment_tab(self) -> None:
        """Builds the enhanced UI for the Back-Order Fulfillment tab."""
        self.fulfillment_tab = self.tab_fulfillment
        self.fulfillment_tab.grid_columnconfigure(1, weight=1)
        self.fulfillment_tab.grid_rowconfigure(0, weight=1)

        # --- Left Pane: Tabbed lists for jobs ---
        left_pane = ctk.CTkTabview(self.fulfillment_tab)
        left_pane.grid(row=0, column=0, padx=10, pady=10, sticky="ns")
        
        self.urgent_jobs_tab = left_pane.add("Urgent Jobs")
        self.inprogress_jobs_tab = left_pane.add("Active Picklists")

        self.urgent_listbox = tk.Listbox(self.urgent_jobs_tab, width=40)
        self.urgent_listbox.pack(fill="both", expand=True)
        self.urgent_listbox.bind("<<ListboxSelect>>", lambda e: self._on_bo_job_select(self.urgent_listbox))

        self.inprogress_listbox = tk.Listbox(self.inprogress_jobs_tab, width=40)
        self.inprogress_listbox.pack(fill="both", expand=True)
        self.inprogress_listbox.bind("<<ListboxSelect>>", lambda e: self._on_bo_job_select(self.inprogress_listbox))

        # --- Right Pane: Details and Actions ---
        right_pane = ctk.CTkFrame(self.fulfillment_tab)
        right_pane.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        right_pane.grid_rowconfigure(1, weight=1)
        right_pane.grid_columnconfigure(0, weight=1)

        # Action Buttons
        action_frame = ctk.CTkFrame(right_pane, fg_color="transparent")
        action_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.generate_picklist_btn = ctk.CTkButton(action_frame, text="Generate Picklist", command=self._preview_manual_picklist, state="disabled")
        self.generate_picklist_btn.pack(side="left", padx=5)

        self.print_picklist_btn = ctk.CTkButton(
            action_frame, 
            text="Print Picklist", 
            command=self._print_manual_picklist, 
            state="disabled"
        )
        self.print_picklist_btn.pack(side="left", padx=5)

        self.reprint_picklist_btn = ctk.CTkButton(action_frame, text="Reprint Updated Picklist", command=self._reprint_manual_picklist, state="disabled")
        self.reprint_picklist_btn.pack(side="left", padx=5)
        
        self.selected_go_number = None

        # Details Treeview
        self.bo_details_tree = ttk.Treeview(right_pane, show="headings")
        self.bo_details_tree.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self._refresh_bo_lists()
    
    def _refresh_bo_lists(self) -> None:
        """Refreshes both listboxes with current job statuses."""
        # Urgent Jobs (Not Started)
        self.urgent_listbox.delete(0, tk.END)
        urgent_jobs = self.dm.get_urgent_go_numbers() 
        for go_num, redcon_status in urgent_jobs:
            self.urgent_listbox.insert(tk.END, f"{go_num} (Urgency: {redcon_status})")
        
        # In-Progress Jobs
        self.inprogress_listbox.delete(0, tk.END)
        inprogress_jobs = self.dm.get_inprogress_go_numbers()
        for go_num, redcon_status in inprogress_jobs:
            self.inprogress_listbox.insert(tk.END, f"{go_num} (Urgency: {redcon_status})")
    

    def _on_bo_job_select(self, listbox_widget: tk.Listbox):
        """Handles selection in either listbox."""
        if not listbox_widget.curselection():
            return

        # Clear selection in the other listbox
        if listbox_widget is self.urgent_listbox:
            self.inprogress_listbox.selection_clear(0, tk.END)
            self.generate_picklist_btn.configure(state="normal")
            self.reprint_picklist_btn.configure(state="disabled")
        else:
            self.urgent_listbox.selection_clear(0, tk.END)
            self.generate_picklist_btn.configure(state="disabled")
            self.reprint_picklist_btn.configure(state="normal")
        
        selection = listbox_widget.get(listbox_widget.curselection())
        self.selected_go_number = selection.split(" ")[0]
        self._populate_bo_details(self.selected_go_number)

    def _populate_bo_details(self, go_number: str):
        """Fills the treeview with all lines for the selected GO number."""
        for item in self.bo_details_tree.get_children():
            self.bo_details_tree.delete(item)

        items = self.dm.get_all_items_for_go(go_number)
        
        columns = [
            "Item #", "Part #", "Status", 
            "Qty Req", "Qty Fulfilled", "Qty Open", 
            "AMO Stock", "KB Stock", "Surplus Stock"
        ]
        self.bo_details_tree.configure(columns=columns)
        for col in columns:
            self.bo_details_tree.heading(col, text=col)
            self.bo_details_tree.column(col, width=100, anchor="center")
        
        for item in items:
            open_qty = item.get('qty_req', 0) - item.get('qty_fulfilled', 0)
            self.bo_details_tree.insert("", "end", values=(
                item.get('item_number', ''),
                item.get('part_number', ''),
                item.get('pick_status', ''),
                item.get('qty_req', 0),
                item.get('qty_fulfilled', 0),
                open_qty,
                item.get('amo_stock_qty', 0),
                item.get('kanban_stock_qty', 0),
                item.get('surplus_stock_qty', 0),
            ))

    def _generate_and_process_picklist(self, preview: bool = False, print_it: bool = False, reprint: bool = False):
        """Core logic for generating, previewing, or printing a picklist."""
        if not self.selected_go_number:
            return

        picklist_items = self.dm.get_all_items_for_go(self.selected_go_number)
        if not picklist_items:
            messagebox.showerror("Error", "Could not retrieve items for this GO number.")
            return

        html_content = picklist_generator.create_picklist_html(picklist_items)

        if preview:
            picklist_generator.preview_picklist(html_content)
        
        if print_it:
            success = picklist_generator.print_picklist(html_content)
            if not success:
                messagebox.showerror("Print Error", "Could not automatically print. Opening preview instead.")
                picklist_generator.preview_picklist(html_content)

        if not reprint:
            item_ids_to_update = [item['id'] for item in picklist_items if item['pick_status'] == 'NOT_STARTED']
            if item_ids_to_update:
                self.dm.update_bo_items_status(item_ids_to_update, "IN_PROGRESS")
            messagebox.showinfo("Picklist Generated", f"Picklist for {self.selected_go_number} has been generated and status updated to IN_PROGRESS.")
        
        self._refresh_bo_lists()
        self._populate_bo_details(self.selected_go_number)

    def _preview_manual_picklist(self):
        self._generate_and_process_picklist(preview=True)

    def _print_manual_picklist(self, reprint=False):
        """Generates a PDF and sends it to a user-selected printer."""
        if not self.selected_go_number:
            return

        # 1. Get the list of available printers
        printers = picklist_generator.get_available_printers()
        if not printers:
            messagebox.showerror("No Printers Found", "Could not find any installed printers on this system.")
            return

        # 2. Ask the user to select a printer
        dialog = PrinterSelectDialog(self, printers)
        selected_printer = dialog.selected_printer

        if not selected_printer:
            messagebox.showinfo("Cancelled", "Print job cancelled.")
            return

        # 3. Generate the HTML and then the PDF
        picklist_items = self.dm.get_all_items_for_go(self.selected_go_number)
        if not picklist_items:
            return
        html_content = picklist_generator.create_picklist_html(picklist_items)
        pdf_path = picklist_generator.generate_picklist_pdf(html_content)

        # 4. Send the PDF to the selected printer
        success = picklist_generator.send_pdf_to_printer(pdf_path, selected_printer)

        if success:
            messagebox.showinfo("Print Job Sent", f"Picklist sent to printer: {selected_printer}")
            # Update status if it's a new picklist
            if not reprint:
                item_ids_to_update = [item['id'] for item in picklist_items if item['pick_status'] == 'NOT_STARTED']
                if item_ids_to_update:
                    self.dm.update_bo_items_status(item_ids_to_update, "IN_PROGRESS")
        else:
            messagebox.showerror("Printing Failed", "Could not send the picklist to the printer.")

        self._refresh_bo_lists()
        self._populate_bo_details(self.selected_go_number)

    def _reprint_manual_picklist(self):
        self._print_manual_picklist(reprint=True)
    
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
