"""Shipper scanning interface."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

import customtkinter as ctk
from tkinter import messagebox, simpledialog

from src.logic import bo_report

from src.config import DB_PATH

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
        self.progress: Optional[ctk.CTkProgressBar] = None

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
        self._csv_cache: Dict[str, tuple[str, int]] | None = None
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

        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # table summarizing progress for all waybills
        self.progress_frame = ctk.CTkFrame(self)
        self.progress_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.lines_frame = ctk.CTkFrame(self.content_frame)
        self.lines_frame.pack(side="left", fill="both", expand=True)

        self.alloc_frame = ctk.CTkFrame(self.content_frame)
        self.alloc_frame.pack(side="left", fill="y", padx=(10, 0))

        font = ctk.CTkFont(size=28, weight="bold")
        self.amo_label = ctk.CTkLabel(self.alloc_frame, text="AMO", width=160, height=60, font=font, fg_color="gray80", corner_radius=8)
        self.amo_label.pack(pady=5, fill="x")
        self.amo_label._base_text = "AMO"  # type: ignore[attr-defined]

        self.kanban_label = ctk.CTkLabel(self.alloc_frame, text="KANBAN", width=160, height=60, font=font, fg_color="gray80", corner_radius=8)
        self.kanban_label.pack(pady=5, fill="x")
        self.kanban_label._base_text = "KANBAN"  # type: ignore[attr-defined]

        self._label_bg = self.amo_label.cget("fg_color")

        self.last_entry_var = ctk.StringVar(value="")
        self.last_entry_label = ctk.CTkLabel(
            self.alloc_frame, textvariable=self.last_entry_var, width=160
        )
        self.last_entry_label.pack(pady=(20, 5), fill="x")

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

        self.refresh_progress_table()

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
    
    def _get_waybill_progress(self) -> List[tuple[str, int, int]]:
        """Return [(waybill, total, remaining)] for all waybills."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT waybill_number, SUM(qty_total) FROM waybill_lines GROUP BY waybill_number"
        )
        totals = {row[0]: int(row[1]) for row in cur.fetchall()}
        cur.execute(
            "SELECT ss.waybill_number, SUM(se.scanned_qty)"
            " FROM scan_events se JOIN scan_sessions ss ON ss.session_id = se.session_id"
            " GROUP BY ss.waybill_number"
        )
        scanned = {row[0]: int(row[1]) for row in cur.fetchall()}
        conn.close()

        progress = []
        for wb, total in totals.items():
            done = scanned.get(wb, 0)
            remaining = max(total - done, 0)
            progress.append((wb, total, remaining))
        progress.sort()
        return progress

    def refresh_progress_table(self) -> None:
        for widget in self.progress_frame.winfo_children():
            widget.destroy()

        headers = ctk.CTkFrame(self.progress_frame)
        headers.pack(fill="x")
        for text, width in [
            ("Waybill", 120),
            ("Total", 80),
            ("Remaining", 80),
            ("Progress", 300),
        ]:
            ctk.CTkLabel(headers, text=text, width=width).pack(side="left")

        rows = self._get_waybill_progress()
        for waybill, total, remaining in rows:
            frame = ctk.CTkFrame(self.progress_frame)
            frame.pack(fill="x", pady=1)
            ctk.CTkLabel(frame, text=waybill, width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(frame, text=str(total), width=80).pack(side="left")
            ctk.CTkLabel(frame, text=str(remaining), width=80).pack(side="left")
            pb = ctk.CTkProgressBar(frame, width=300)
            pb.pack(side="left", padx=5)
            ratio = (total - remaining) / total if total else 0
            pb.set(ratio)
            pb.configure(progress_color=_color_from_ratio(ratio))

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
            expected = sum(
                line.qty_total for line in self.lines if line.part == part
            )
            remaining = expected - total
            allocated = ", ".join(
                f"{line.subinv}:{line.scanned}" for line in self.lines if line.part == part
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
            lines.sort(key=lambda line: 0 if "AMO" in line.subinv else 1)
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
            ("Total", 80),
            ("Progress", 300),
            ("Remaining", 80),
        ]:
            ctk.CTkLabel(headers, text=text, width=width).pack(side="left")

        for part, lines in part_groups.items():
            row_frame = ctk.CTkFrame(self.lines_frame)
            row_frame.pack(fill="x", pady=1)
            ctk.CTkLabel(row_frame, text=part, width=200, anchor="w").pack(side="left")

            total_qty = sum(l.qty_total for l in lines)
            ctk.CTkLabel(row_frame, text=str(total_qty), width=80).pack(side="left")

            pb = ctk.CTkProgressBar(row_frame, width=300)
            pb.pack(side="left", padx=5)
            rem_label = ctk.CTkLabel(row_frame, width=80)
            rem_label.pack(side="left")

            for ln in lines:
                ln.progress = pb
                ln.rem_label = rem_label
            self._update_line_widgets(lines[0])

        self.refresh_progress_table()

        self.scan_entry.focus_set()

    def _update_line_widgets(self, line: _Line) -> None:
        group = [ln for ln in self.lines if ln.part == line.part]
        total_qty = sum(l.qty_total for l in group)
        total_scanned = sum(l.scanned for l in group)
        ratio = total_scanned / total_qty if total_qty else 0
        if line.progress is not None:
            line.progress.set(ratio)
            line.progress.configure(progress_color=_color_from_ratio(ratio))
        if line.rem_label is not None:
            line.rem_label.configure(text=str(total_qty - total_scanned))

    def _flash_alloc_label(self, label: ctk.CTkLabel, qty: int, color) -> None:
            
        label.configure(text=f"{label._base_text} +{qty}", fg_color=color)  # type: ignore[attr-defined]

        if getattr(label, "_after_id", None):
            self.after_cancel(label._after_id) # type: ignore[attr-defined]

        def reset() -> None:
            label.configure(text=label._base_text, fg_color=self._label_bg) # type: ignore[attr-defined]

        label._after_id = self.after(1500, reset)  # type: ignore[attr-defined]

    def _update_alloc_labels(self, allocations: Dict[str, int]) -> None:
        if allocations.get("AMO"):
            self._flash_alloc_label(self.amo_label, allocations["AMO"],"red")
        if allocations.get("KANBAN"):
            self._flash_alloc_label(self.kanban_label, allocations["KANBAN"],"green")

    def _update_last_entry(self, part: str, qty: int, allocations: Dict[str, int]) -> None:
        """Display the details of the most recent scan."""
        alloc_parts = []
        if allocations.get("AMO"):
            alloc_parts.append(f"AMO {allocations['AMO']}")
        if allocations.get("KANBAN"):
            alloc_parts.append(f"KANBAN {allocations['KANBAN']}")
        alloc_text = ", ".join(alloc_parts)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.last_entry_var.set(f"{timestamp} - {part} x{qty} -> {alloc_text}")

    def _load_csv_cache(self) -> None:
        """Load the part identifier CSV into ``self._csv_cache``."""
        cache: Dict[str, tuple[str, int]] = {}
        path = Path(self.csv_path)
        if path.is_file():
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    part = (row.get("part_number") or "").strip()
                    upc = (row.get("upc_code") or "").strip()
                    qty = row.get("qty") or "1"
                    try:
                        qty_int = int(qty)
                    except ValueError:
                        qty_int = 1
                    if upc:
                        cache[upc] = (part, qty_int)
        self._csv_cache = cache

    def _resolve_part(self, code: str) -> tuple[str, int]:
        code = code.strip()
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT part_number, qty FROM part_identifiers WHERE part_number=? OR upc_code=?",
                (code, code),
            )
            row = cur.fetchone()
        except sqlite3.OperationalError:
            cur.execute(
                "SELECT part_number FROM part_identifiers WHERE part_number=? OR upc_code=?",
                (code, code),
            )
            result = cur.fetchone()
            row = (result[0], 1) if result else None
        conn.close()
        if row:
            part, qty = row[0], row[1]
            qty = int(qty) if qty is not None else 1
            return part, qty

        self._load_csv_cache()
        assert self._csv_cache is not None
        part, qty = self._csv_cache.get(code, (code, 1))
        return part, qty

    def process_scan(self, event=None) -> None:
        raw = self.scan_var.get().strip()
        if not raw:
            return
        qty = self.qty_var.get()
        if qty <= 0:
            messagebox.showwarning("Invalid qty", "Quantity must be > 0")
            return
        part, box_qty = self._resolve_part(raw)
        if qty == 1:
            qty = box_qty
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
        allocations: Dict[str, int] = {"AMO": 0, "KANBAN": 0}

        matching.sort(key=lambda line: 0 if "AMO" in line.subinv else 1)
        total_remaining = sum(l.remaining() for l in matching)
        while qty > total_remaining:
            new_qty = simpledialog.askinteger(
                "Over scan",
                f"Only {total_remaining} remaining for {part}. Enter new quantity:",
                parent=self,
            )
            if new_qty is None:
                self.scan_var.set("")
                self.qty_var.set(1)
                return
            qty = new_qty

        remaining_qty = qty
        for line in matching:
            alloc = min(line.remaining(), remaining_qty)
            if alloc:
                line.scanned += alloc
                remaining_qty -= alloc
                if "AMO" in line.subinv:
                    allocations["AMO"] += alloc
                elif "KANBAN" in line.subinv:
                    allocations["KANBAN"] += alloc
                self._update_line_widgets(line)
            if remaining_qty == 0:
                break

        if remaining_qty > 0:
            messagebox.showwarning("Over scan", "Quantity exceeds expected")
            return

        self._update_alloc_labels(allocations)

        self._update_last_entry(part, qty, allocations)

        self._insert_event(part, qty, raw)
        self.refresh_progress_table()
        self.scan_var.set("")
        self.qty_var.set(1)

        if all(line.remaining() == 0 for line in self.lines):
            all_done = all(rem == 0 for _, _, rem in self._get_waybill_progress())
            if all_done:
                if messagebox.askyesno(
                    "Waybills complete",
                    "All waybills finished. Close interface?",
                ):
                    self._finish_session()
            else:
                messagebox.showinfo("Waybill finished", "Current waybill completed")

    # end of class


def start_shipper_interface(
    user_id: int,
    db_path: str = DB_PATH,
    csv_path: str = PART_IDENTIFIERS_CSV,
) -> None:
    """Launch the shipper interface for ``user_id``."""
    app = ShipperWindow(user_id, db_path, csv_path)
    app.mainloop()
