"""Shipper scanning interface."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

import customtkinter as ctk
from tkinter import messagebox

from logic import bo_report

from config import DB_PATH

#DB_PATH = "receiving_tracker.db"
PART_IDENTIFIERS_CSV = "data/part_identifiers.csv"


def _color_from_ratio(ratio: float) -> str:
    """Return a red→green hex color based on ``ratio`` (0..1)."""
    ratio = max(0.0, min(1.0, ratio))
    red = int(255 * (1 - ratio))
    green = int(255 * ratio)
    return f"#{red:02x}{green:02x}00"


SUBINV_MAP = {
    "DRV-AMO": "AMO",
    "DRV-RM": "KANBAN",
}


class _Line:
    def __init__(
        self,
        rowid: int,
        part: str,
        qty: int,
        subinv: str,
        subinv_code: str | None = None,
    ) -> None:
        self.rowid = rowid
        self.part = part
        self.qty_total = qty
        self.subinv = subinv
        # keep the original subinv code for potential DB updates
        self.subinv_code = subinv_code if subinv_code is not None else subinv
        self.scanned = 0
        self.rem_label: Optional[ctk.CTkLabel] = None
        self.progress = ctk.CTkProgressBar(master=None)

    def remaining(self) -> int:
        return self.qty_total - self.scanned


class ShipperWindow(ctk.CTk):
    def __init__(
        self,
        user_id: int,
        db_path: str = DB_PATH,
        csv_path: str = PART_IDENTIFIERS_CSV,
    ):
        super().__init__()
        self.db_path = db_path
        self.csv_path = csv_path
        self._csv_cache: Dict[str, str] = {}#| None = None
        self.user_id = user_id
        self.session_id = self._get_session()
        self.bo_df: Optional[pd.DataFrame] = None

        self.title("Shipper Interface")
        self.geometry("900x600")

        self.waybills = self._fetch_waybills()
        if not self.waybills:
            messagebox.showinfo("Info", "No active waybills in database")
            self.destroy()
            return

        self.waybill_var = ctk.StringVar(value=self.waybills[0])
        ctk.CTkLabel(self, text="Select Waybill:").pack(pady=5)
        menu = ctk.CTkOptionMenu(self, values=self.waybills, variable=self.waybill_var, command=self.load_waybill)
        menu.pack()

        self.lines_frame = ctk.CTkFrame(self)
        self.lines_frame.pack(fill="both", expand=True, padx=10, pady=10)

        controls = ctk.CTkFrame(self)
        controls.pack(fill="x", pady=5)

        self.qty_var = ctk.IntVar(value=1)
        ctk.CTkLabel(controls, text="Qty:").pack(side="left")
        self.qty_entry = ctk.CTkEntry(controls, textvariable=self.qty_var, width=60)
        self.qty_entry.pack(side="left", padx=(0, 20))

        self.scan_var = ctk.StringVar()
        self.scan_entry = ctk.CTkEntry(controls, textvariable=self.scan_var)
        self.scan_entry.pack(side="left", fill="x", expand=True)
        self.scan_entry.bind("<Return>", self.process_scan)

        finish_btn = ctk.CTkButton(
            controls, text="Finish Waybill", command=self.manual_finish
        )
        finish_btn.pack(side="left", padx=(20, 0))

        self.lines: List[_Line] = []
        self.load_waybill(self.waybill_var.get())

    # DB helpers -----------------------------------------------------
    def _get_session(self) -> int:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT session_id FROM scan_sessions "
            "WHERE user_id=? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1",
            (self.user_id,),
        )
        row = cur.fetchone()
        if row:
            session_id = int(row[0])
        else:
            start_time = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO scan_sessions (user_id, waybill_number, start_time) VALUES (?, ?, ?)",
                (self.user_id, "", start_time),
            )
            session_id = cur.lastrowid or 0
            conn.commit()
        conn.close()
        return session_id

    def _fetch_waybills(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT waybill_number FROM waybill_lines")
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows

    def _fetch_scans(self, waybill: str) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT se.part_number, SUM(se.scanned_qty) FROM scan_events se "
            "JOIN scan_sessions ss ON ss.session_id = se.session_id "
            "WHERE ss.waybill_number = ? GROUP BY se.part_number",
            (waybill,),
        )
        data = {row[0]: int(row[1]) for row in cur.fetchall()}
        conn.close()
        return data

    def load_bo_report(self, filepath: str) -> None:
        """Load the BO Excel file for later use."""
        try:
            self.bo_df = bo_report.load_bo_excel(filepath)
        except NotImplementedError:
            self.bo_df = None
        except Exception as exc:  # pragma: no cover - placeholder
            messagebox.showerror("BO load error", str(exc))

    def _insert_event(self, part: str, qty: int, raw: str) -> None:
        timestamp = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO scan_events (session_id, part_number, scanned_qty, timestamp, raw_scan) "
            "VALUES (?, ?, ?, ?, ?)",
            (self.session_id, part, qty, timestamp, raw),
        )
        conn.commit()
        conn.close()

    def _update_session_waybill(self, waybill: str) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "UPDATE scan_sessions SET waybill_number=? WHERE session_id=?",
            (waybill, self.session_id),
        )
        conn.commit()
        conn.close()

    def _finish_session(self) -> None:
        end_time = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "UPDATE scan_sessions SET end_time=? WHERE session_id=?",
            (end_time, self.session_id),
        )
        conn.commit()
        conn.close()

        self._record_summary()
        messagebox.showinfo("Waybill finished", "Scan summary saved")
        self.destroy()

    def manual_finish(self) -> None:
        if messagebox.askyesno("Confirm", "Finish current waybill?"):
            self._finish_session()

    def _record_summary(self) -> None:
        scans = self._fetch_scans(self.waybill_var.get())
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        for part, total in scans.items():
            expected = sum(l.qty_total for l in self.lines if l.part == part)
            remaining = expected - total
            allocated = ", ".join(
                f"{l.subinv}:{l.scanned}" for l in self.lines if l.part == part
            )
            cur.execute(
                "INSERT INTO scan_summary (session_id, user_id, part_number, total_scanned, expected_qty, remaining_qty, allocated_to, reception_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.session_id,
                    self.user_id,
                    part,
                    total,
                    expected,
                    remaining,
                    allocated,
                    datetime.utcnow().date().isoformat(),
                ),
            )
        conn.commit()
        conn.close()

    # Interface logic ------------------------------------------------
    def load_waybill(self, waybill: str) -> None:
        self._update_session_waybill(waybill)
        scans = self._fetch_scans(waybill)

        for widget in self.lines_frame.winfo_children():
            widget.destroy()
        self.lines = []

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, part_number, qty_total, subinv FROM waybill_lines WHERE waybill_number=? ORDER BY part_number",
            (waybill,),
        )
        rows = cur.fetchall()
        conn.close()

        for row in rows:
            code = row[3]
            #friendly = SUBINV_MAP.get(code, code)
            friendly: str = SUBINV_MAP.get(code) or code
            line = _Line(row[0], row[1], int(row[2]), friendly, code)
            self.lines.append(line)

        # allocate scanned qty across lines (AMO first)
        part_groups: Dict[str, List[_Line]] = {}
        for line in self.lines:
            part_groups.setdefault(line.part, []).append(line)
        for part, lines in part_groups.items():
            lines.sort(key=lambda l: 0 if "AMO" in l.subinv else 1)
            remaining = scans.get(part, 0)
            for ln in lines:
                alloc = min(ln.qty_total, remaining)
                ln.scanned = alloc
                remaining -= alloc

        # Build UI table
        headers = ctk.CTkFrame(self.lines_frame)
        headers.pack(fill="x")
        for text, width in [
            ("Part", 200),
            ("Subinv", 80),
            ("Remaining", 80),
            ("Progress", 300),
        ]:
            ctk.CTkLabel(headers, text=text, width=width).pack(side="left")

        for line in self.lines:
            row_frame = ctk.CTkFrame(self.lines_frame)
            row_frame.pack(fill="x", pady=1)
            ctk.CTkLabel(row_frame, text=line.part, width=200, anchor="w").pack(side="left")
            ctk.CTkLabel(row_frame, text=line.subinv, width=80).pack(side="left")
            rem_label = ctk.CTkLabel(row_frame, width=80)
            rem_label.pack(side="left")
            pb = ctk.CTkProgressBar(row_frame, width=300)
            pb.pack(side="left", padx=5)
            line.progress = pb
            line.rem_label = rem_label
            self._update_line_widgets(line)

        self.scan_entry.focus_set()

    def _update_line_widgets(self, line: _Line) -> None:
        ratio = line.scanned / line.qty_total if line.qty_total else 0
        line.progress.set(ratio)
        line.progress.configure(progress_color=_color_from_ratio(ratio))
        if line.rem_label is not None:
            line.rem_label.configure(text=str(line.remaining()))

    def _load_csv_cache(self) -> None:
        """Load the part identifier CSV into ``self._csv_cache``."""
        self._csv_cache = {}
        path = Path(self.csv_path)
        if not path.is_file():
            return
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                part = (row.get("part_number") or "").strip()
                upc = (row.get("upc_code") or "").strip()
                alt = (row.get("alt_code") or "").strip()
                if upc:
                    self._csv_cache[upc] = part
                if alt:
                    self._csv_cache[alt] = part

    def _resolve_part(self, code: str) -> str:
        code = code.strip()
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT part_number FROM part_identifiers WHERE part_number=? OR upc_code=? OR alt_code=?",
            (code, code, code),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]

        if self._csv_cache is None:
            self._load_csv_cache()
        assert self._csv_cache is not None
        return self._csv_cache.get(code, code)

    def process_scan(self, event=None) -> None:
        raw = self.scan_var.get().strip()
        if not raw:
            return
        qty = self.qty_var.get()
        if qty <= 0:
            messagebox.showwarning("Invalid qty", "Quantity must be > 0")
            return
        part = self._resolve_part(raw)
        if self.bo_df is not None:
            try:
                bo_report.find_bo_match(part, self.bo_df)
            except NotImplementedError:
                pass

        matching = [ln for ln in self.lines if ln.part == part]
        if not matching:
            messagebox.showwarning("Unknown part", f"{part} not on waybill")
            self.scan_var.set("")
            self.qty_var.set(1)
            return

        remaining_qty = qty
        matching.sort(key=lambda l: 0 if "AMO" in l.subinv else 1)
        for line in matching:
            alloc = min(line.remaining(), remaining_qty)
            if alloc:
                line.scanned += alloc
                remaining_qty -= alloc
                self._update_line_widgets(line)
            if remaining_qty == 0:
                break

        if remaining_qty > 0:
            messagebox.showwarning("Over scan", "Quantity exceeds expected")
            return

        part = self._resolve_part(raw)
        if part is None:
            messagebox.showwarning("Invalid part", "Could not resolve scanned code")
            return
        self._insert_event(part, qty, raw)
        self.scan_var.set("")
        self.qty_var.set(1)

        if all(l.remaining() == 0 for l in self.lines):
            self._finish_session()

    # end of class


def start_shipper_interface(
    user_id: int,
    db_path: str = DB_PATH,
    csv_path: str = PART_IDENTIFIERS_CSV,
) -> None:
    """Launch the shipper interface for ``user_id``."""
    app = ShipperWindow(user_id, db_path, csv_path)
    app.mainloop()
