"""Shipper scanning interface."""

from __future__ import annotations

import logging

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

import pandas as pd
import platform

import customtkinter as ctk
from tkinter import messagebox

from src.logic import bo_report

from src.config import DB_PATH, APPEARANCE_MODE
from src.data_manager import DataManager
from src.logic.scanning import Line, ScannerLogic

PART_IDENTIFIERS_CSV = "data/part_ids.csv"

logger = logging.getLogger(__name__)


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


def _last_working_day(ref: date) -> date:
    """Return the previous weekday for ``ref`` (skip weekends)."""
    day = ref - timedelta(days=1)
    while day.weekday() >= 5:  # 5=Sat, 6=Sun
        day -= timedelta(days=1)
    return day



class ShipperWindow(ctk.CTk):
    def __init__(
        self,
        user_id: int,
        db_path: str = DB_PATH,
        csv_path: str = PART_IDENTIFIERS_CSV,
    ):
        super().__init__()
        self.db_path = db_path
        self.dm = DataManager(db_path)
        self.csv_path = csv_path
        self.logic = ScannerLogic(self.dm, csv_path)
        self.user_id = user_id
        self.session_id: Optional[int] = None
        self._summary_recorded: bool = False
        self.bo_df: Optional[pd.DataFrame] = None

        self.title("Shipper Interface")
        self.geometry("900x600")
        if hasattr(self, "state"):
            try:
                self.state("zoomed")
            except Exception:
                pass
        ctk.set_appearance_mode(APPEARANCE_MODE)

        today = datetime.utcnow().date()
        all_wbs = self._fetch_waybills(None)
        import_dates = self.dm.get_waybill_import_dates()
        target = _last_working_day(today)
        self.today_waybills = []
        for wb in all_wbs:
            date_str = import_dates.get(wb)
            try:
                imp = datetime.fromisoformat(date_str).date() if date_str else None
            except Exception:
                imp = None
            if imp == target:
                self.today_waybills.append(wb)
        self.other_waybills = [
            wb for wb in self.dm.fetch_incomplete_waybills() if wb not in self.today_waybills
        ]
        self.waybills = self.today_waybills + self.other_waybills
        if not self.today_waybills and not self.other_waybills:
            messagebox.showinfo("Info", "No active waybills in database")
            self.destroy()
            return

        default = self.today_waybills[0] if self.today_waybills else (
            self.other_waybills[0] if self.other_waybills else ""
        )
        self.waybill_var = ctk.StringVar(value=default)
        if hasattr(self, "columnconfigure"):
            try:
                self.columnconfigure(0, weight=1)
                self.columnconfigure(1, weight=1)
                self.rowconfigure(4, weight=1)
            except Exception:
                pass

        ctk.CTkLabel(self, text="Today's Waybills:").grid(row=0, column=0, sticky="e", padx=(10, 5), pady=5)
        today_menu = ctk.CTkOptionMenu(
            self,
            values=self.today_waybills,
            variable=self.waybill_var,
            command=self.load_waybill,
            width=200,
        )
        today_menu.grid(row=0, column=1, sticky="w", pady=5)
        self.today_menu = today_menu
        if not self.today_waybills:
            self.waybill_var.set("")
            self.today_menu.configure(values=[])

        ctk.CTkLabel(self, text="Older/Incomplete:").grid(row=1, column=0, sticky="e", padx=(10, 5), pady=5)
        other_menu = ctk.CTkOptionMenu(
            self,
            values=self.other_waybills,
            variable=self.waybill_var,
            command=self.load_waybill,
            width=200,
        )
        other_menu.grid(row=1, column=1, sticky="w", pady=5)
        self.other_menu = other_menu

        self.list_status = ctk.CTkLabel(
            self,
            text="Today's waybills" if self.today_waybills else "Incomplete waybills",
        )
        ctk.CTkButton(self, text="Show All Today's Waybills", command=self._load_all_today).grid(row=2, column=0, pady=(0,5))
        ctk.CTkButton(self, text="Show All Incomplete Waybills", command=self._load_all_incomplete).grid(row=2, column=1, pady=(0,5))

        self.list_status.grid(row=3, column=0, columnspan=2, pady=(0, 5))

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        if hasattr(self.main_frame, "grid_columnconfigure"):
            try:
                self.main_frame.grid_columnconfigure(0, weight=3)
                self.main_frame.grid_columnconfigure(1, weight=1)
                self.main_frame.grid_rowconfigure(0, weight=1)
            except Exception:
                pass

        self.lines_frame = ctk.CTkFrame(self.main_frame)
        self.lines_frame.grid(row=0, column=0, sticky="nsew")

        self.sidebar_frame = ctk.CTkFrame(self.main_frame)
        self.sidebar_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # table summarizing progress for all waybills
        self.progress_frame = ctk.CTkFrame(self.sidebar_frame)
        self.progress_frame.pack(fill="x", pady=(0, 10))

        self.alloc_frame = ctk.CTkFrame(self.sidebar_frame)
        self.alloc_frame.pack(fill="x", pady=(0, 10))

        font = ctk.CTkFont(size=28, weight="bold")
        self.amo_label = ctk.CTkLabel(self.alloc_frame, text="AMO", width=160, height=60, font=font, fg_color="gray80", corner_radius=8)
        self.amo_label.pack(pady=5, fill="x")
        self.amo_label._base_text = "AMO"  # type: ignore[attr-defined]

        self.kanban_label = ctk.CTkLabel(self.alloc_frame, text="KANBAN", width=160, height=60, font=font, fg_color="gray80", corner_radius=8)
        self.kanban_label.pack(pady=5, fill="x")
        self.kanban_label._base_text = "KANBAN"  # type: ignore[attr-defined]

        self._label_bg = self.amo_label.cget("fg_color")

        self.last_entries: List[str] = []
        self.history_box = ctk.CTkTextbox(self.sidebar_frame, width=200, height=150)
        self.history_box.pack(fill="both", pady=(5, 5))
        self.history_box.configure(state="disabled")

        controls = ctk.CTkFrame(self.main_frame)
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

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

        logout_btn = ctk.CTkButton(
            controls, text="End Session", command=self.manual_logout
        )
        logout_btn.pack(side="left", padx=(20, 0))

        self.lines: List[Line] = []
        self.load_waybill(self.waybill_var.get())

        self.refresh_progress_table()

        # handle window close the same as logout
        try:
            self.protocol("WM_DELETE_WINDOW", self.manual_logout)
        except Exception:
            pass

    # DB helpers -----------------------------------------------------
    def _get_session(self, waybill: str) -> int:
        return self.dm.create_session(self.user_id, waybill)

    def _fetch_waybills(self, date: str | None = None) -> List[str]:
        return self.dm.fetch_waybills(date)

    def _show_all_waybills(self) -> None:
        today = datetime.utcnow().date()
        all_wbs = self._fetch_waybills(None)
        if not all_wbs:
            messagebox.showinfo("Info", "No active waybills in database")
            return
        import_dates = self.dm.get_waybill_import_dates()
        target = _last_working_day(today)
        self.today_waybills = []
        for wb in all_wbs:
            date_str = import_dates.get(wb)
            try:
                imp = datetime.fromisoformat(date_str).date() if date_str else None
            except Exception:
                imp = None
            if imp == target:
                self.today_waybills.append(wb)
        self.other_waybills = [
            wb for wb in self.dm.fetch_incomplete_waybills() if wb not in self.today_waybills
        ]
        self.waybills = self.today_waybills + self.other_waybills
        self.today_menu.configure(values=self.today_waybills)
        self.other_menu.configure(values=self.other_waybills)
        if self.today_waybills:
            self.waybill_var.set(self.today_waybills[0])
        elif self.other_waybills:
            self.waybill_var.set(self.other_waybills[0])
        if self.waybill_var.get():
            self.load_waybill(self.waybill_var.get())
        self.refresh_progress_table()

    def _fetch_scans(self, waybill: str) -> Dict[str, int]:
        return self.dm.fetch_scans(waybill)
    
    def _get_waybill_progress(self) -> List[tuple[str, int, int]]:
        """Return [(waybill, total, remaining)] for all waybills."""
        return self.dm.get_waybill_progress()

    def refresh_progress_table(self) -> None:
        for widget in self.progress_frame.winfo_children():
            widget.destroy()

        header_font = ctk.CTkFont(size=20, weight="bold")
        cell_font = ctk.CTkFont(size=18)

        for idx, (text, width) in enumerate([
            ("Waybill", 120),
            ("Total", 80),
            ("Remaining", 80),
            ("Progress", 300),
        ]):
            lbl = ctk.CTkLabel(self.progress_frame, text=text, width=width, font=header_font)
            lbl.grid(row=0, column=idx, sticky="w")

        rows = self._get_waybill_progress()
        dates = self.dm.get_waybill_dates()
        today = datetime.utcnow().date()
        target = _last_working_day(today)
        for row_idx, (waybill, total, remaining) in enumerate(rows, start=1):
            date_str = dates.get(waybill, "")
            try:
                parsed = datetime.fromisoformat(date_str).date() if date_str else None
            except Exception:
                parsed = None
            color = (
                "orange" if parsed and parsed < target and remaining > 0 else None
            )
            kwargs = dict(
                text=f"{waybill} ({date_str})", width=120, anchor="w", font=cell_font
            )
            if color:
                kwargs["text_color"] = color
            lbl = ctk.CTkLabel(self.progress_frame, **kwargs)
            lbl.grid(row=row_idx, column=0, sticky="w", pady=1)

            ctk.CTkLabel(
                self.progress_frame, text=str(total), width=80, font=cell_font
            ).grid(row=row_idx, column=1, sticky="w")

            ctk.CTkLabel(
                self.progress_frame, text=str(remaining), width=80, font=cell_font
            ).grid(row=row_idx, column=2, sticky="w")

            pb = ctk.CTkProgressBar(self.progress_frame, width=300)
            pb.grid(row=row_idx, column=3, sticky="ew", padx=5)
            ratio = (total - remaining) / total if total else 0
            pb.set(ratio)
            pb.configure(progress_color=_color_from_ratio(ratio))

    def _load_list(self, waybills: List[str], label: str) -> None:
        if not waybills:
            for widget in self.lines_frame.winfo_children():
                widget.destroy()
            self.lines = []
            for widget in self.progress_frame.winfo_children():
                widget.destroy()
            self.list_status.configure(text=label)
            self.waybill_var.set("")
            return
        self.waybill_var.set(waybills[0])
        self.load_waybills(waybills)
        self.list_status.configure(text=label)

    def _load_all_today(self) -> None:
        self._load_list(self.today_waybills, "Today's waybills")

    def _load_all_incomplete(self) -> None:
        incompletes = self.dm.fetch_incomplete_waybills()
        import_dates = self.dm.get_waybill_import_dates()
        today = datetime.utcnow().date()
        target = _last_working_day(today)
        old = [wb for wb in incompletes if import_dates.get(wb) != target]
        self._load_list(old, "Incomplete waybills")

    def load_bo_report(self, filepath: str) -> None:
        """Load the BO Excel file for later use."""
        try:
            self.bo_df = bo_report.load_bo_excel(filepath)
        except NotImplementedError:
            self.bo_df = None
        except Exception as exc:  # pragma: no cover - placeholder
            messagebox.showerror("BO load error", str(exc))

    def _insert_event(self, part: str, qty: int, raw: str) -> None:
        if self.session_id is not None:
            self.dm.insert_scan_event(
                self.session_id,
                self.waybill_var.get(),
                part,
                qty,
                raw_scan=raw,
            )

    def _update_session_waybill(self, waybill: str) -> None:
        if self.session_id is not None:
            self.dm.update_session_waybill(self.session_id, waybill)

    def _finish_session(self) -> None:
        self.record_partial_summary()
        messagebox.showinfo("Waybill finished", "Scan summary saved")
        self.last_entries.clear()
        try:
            self.history_box.configure(state="normal")
            self.history_box.delete("1.0", "end")
            self.history_box.configure(state="disabled")
        except Exception:
            pass
        self.destroy()

    def manual_finish(self) -> None:
        if messagebox.askyesno("Confirm", "Finish current waybill?"):
            self._finish_session()

    def manual_logout(self) -> None:
        if messagebox.askyesno("Confirm", "End scanning session and exit?"):
            self._finish_session()

    def _record_summary(self) -> None:
        scans = self._fetch_scans(self.waybill_var.get())
        rows = []
        for part, total in scans.items():
            expected = sum(
                line.qty_total for line in self.lines if line.part == part
            )
            remaining = expected - total
            allocated = ", ".join(
                f"{line.subinv}:{line.scanned}" for line in self.lines if line.part == part
            )

            rows.append(
                (
                    self.session_id,
                    self.waybill_var.get(),
                    self.user_id,
                    part,
                    total,
                    expected,
                    remaining,
                    allocated,
                    datetime.utcnow().date().isoformat(),
                )
            )
        if rows:
            self.dm.insert_scan_summaries(rows)

    def record_partial_summary(self) -> None:
        """Write a summary row and close the session if not already done."""
        if self.session_id is None or self._summary_recorded:
            return
        self._record_summary()
        self.dm.end_session(self.session_id)
        self.session_id = None
        self._summary_recorded = True

    # Interface logic ------------------------------------------------
    def load_waybill(self, waybill: str) -> None:
        if self.session_id is None:
            self.session_id = self._get_session(waybill)
        else:
            self._update_session_waybill(waybill)
        scans = self._fetch_scans(waybill)

        for widget in self.lines_frame.winfo_children():
            widget.destroy()
        self.lines = []

        rows = self.dm.get_waybill_lines(waybill)

        for row in rows:
            code = row[3]
            #friendly = SUBINV_MAP.get(code, code)
            friendly: str = SUBINV_MAP.get(code) or code
            line = Line(row[0], row[1].upper(), int(row[2]), friendly, code)
            self.lines.append(line)

        # allocate scanned qty across lines (AMO first)
        part_groups: Dict[str, List[Line]] = {}
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
        header_font = ctk.CTkFont(size=20, weight="bold")
        cell_font = ctk.CTkFont(size=18)
        for text, width in [
            ("Part", 200),
            ("Total", 80),
            ("Progress", 300),
            ("Remaining", 80),
        ]:
            ctk.CTkLabel(headers, text=text, width=width, font=header_font).pack(side="left")

        for part, lines in part_groups.items():
            row_frame = ctk.CTkFrame(self.lines_frame)
            row_frame.pack(fill="x", pady=1)
            ctk.CTkLabel(row_frame, text=part, width=200, anchor="w", font=cell_font).pack(side="left")

            total_qty = sum(l.qty_total for l in lines)
            ctk.CTkLabel(row_frame, text=str(total_qty), width=80, font=cell_font).pack(side="left")

            pb = ctk.CTkProgressBar(row_frame, width=300)
            pb.pack(side="left", padx=5)
            rem_label = ctk.CTkLabel(row_frame, width=80, font=cell_font)
            rem_label.pack(side="left")

            for ln in lines:
                ln.progress = pb # type: ignore[attr-defined]
                ln.rem_label = rem_label # type: ignore[attr-defined]
            self._update_line_widgets(lines[0])

        self.refresh_progress_table()

        self.scan_entry.focus_set()

    def load_waybills(self, waybills: List[str]) -> None:
        if not waybills:
            for widget in self.lines_frame.winfo_children():
                widget.destroy()
            self.lines = []
            for widget in self.progress_frame.winfo_children():
                widget.destroy()
            return
        if self.session_id is None:
            self.session_id = self._get_session(waybills[0])
        else:
            self._update_session_waybill(waybills[0])
        scans: Dict[str, int] = {}
        for wb in waybills:
            data = self._fetch_scans(wb)
            for part, qty in data.items():
                scans[part] = scans.get(part, 0) + qty

        for widget in self.lines_frame.winfo_children():
            widget.destroy()
        self.lines = []

        rows = self.dm.get_waybill_lines_multi(waybills)
        for row in rows:
            code = row[3]
            friendly = SUBINV_MAP.get(code) or code
            line = Line(row[0], row[1].upper(), int(row[2]), friendly, code)
            self.lines.append(line)

        part_groups: Dict[str, List[Line]] = {}
        for line in self.lines:
            part_groups.setdefault(line.part, []).append(line)
        for part, lines in part_groups.items():
            lines.sort(key=lambda line: 0 if "AMO" in line.subinv else 1)
            remaining = scans.get(part, 0)
            for ln in lines:
                alloc = min(ln.qty_total, remaining)
                ln.scanned = alloc
                remaining -= alloc

        headers = ctk.CTkFrame(self.lines_frame)
        headers.pack(fill="x")
        header_font = ctk.CTkFont(size=20, weight="bold")
        cell_font = ctk.CTkFont(size=18)
        for text, width in [
            ("Part", 200),
            ("Total", 80),
            ("Progress", 300),
            ("Remaining", 80),
        ]:
            ctk.CTkLabel(headers, text=text, width=width, font=header_font).pack(side="left")

        for part, lines in part_groups.items():
            row_frame = ctk.CTkFrame(self.lines_frame)
            row_frame.pack(fill="x", pady=1)
            ctk.CTkLabel(row_frame, text=part, width=200, anchor="w", font=cell_font).pack(side="left")

            total_qty = sum(l.qty_total for l in lines)
            ctk.CTkLabel(row_frame, text=str(total_qty), width=80, font=cell_font).pack(side="left")

            pb = ctk.CTkProgressBar(row_frame, width=300)
            pb.pack(side="left", padx=5)
            rem_label = ctk.CTkLabel(row_frame, width=80, font=cell_font)
            rem_label.pack(side="left")

            for ln in lines:
                ln.progress = pb  # type: ignore[attr-defined]
                ln.rem_label = rem_label  # type: ignore[attr-defined]
            self._update_line_widgets(lines[0])

        self.refresh_progress_table()

        self.scan_entry.focus_set()

    def _update_line_widgets(self, line: Line) -> None:
        group = [ln for ln in self.lines if ln.part == line.part]
        total_qty = sum(l.qty_total for l in group)
        total_scanned = sum(l.scanned for l in group)
        ratio = total_scanned / total_qty if total_qty else 0
        if line.progress is not None: # type: ignore[attr-defined]
            line.progress.set(ratio) # type: ignore[attr-defined]
            line.progress.configure(progress_color=_color_from_ratio(ratio)) # type: ignore[attr-defined]
        if line.rem_label is not None: # type: ignore[attr-defined]
            line.rem_label.configure(text=str(total_qty - total_scanned)) # type: ignore[attr-defined]

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

    def _alert_beep(self) -> None:
        """Emit an audible alert if possible."""
        try:
            self.bell()
        except Exception:
            pass
        if platform.system() == "Windows":
            try:
                import winsound
                winsound.Beep(1000, 200)
            except Exception:
                pass

    def _update_last_entry(self, part: str, qty: int, allocations: Dict[str, int]) -> None:
        """Display the details of the most recent scan."""
        alloc_parts = []
        if allocations.get("AMO"):
            alloc_parts.append(f"AMO {allocations['AMO']}")
        if allocations.get("KANBAN"):
            alloc_parts.append(f"KANBAN {allocations['KANBAN']}")
        alloc_text = ", ".join(alloc_parts)
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"{timestamp} - {part} x{qty} -> {alloc_text}"
        self.last_entries.append(entry)
        self.last_entries = self.last_entries[-10:]
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.insert("end", "\n".join(self.last_entries))
        self.history_box.see("end")
        self.history_box.configure(state="disabled")

    def process_scan(self, event=None) -> None:
        raw = self.scan_var.get().strip()
        if not raw:
            return
        qty = self.qty_var.get()
        if qty <= 0:
            messagebox.showwarning("Invalid qty", "Quantity must be > 0")
            self._alert_beep()
            return
        part, box_qty = self.logic.resolve_part(raw)
        part = part.upper()
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
            self._alert_beep()
            self.scan_var.set("")
            self.qty_var.set(1)
            return

        try:
            allocations = self.logic.allocate(matching, qty)
        except ValueError:
            logger.warning("Over scan detected for part %s (qty=%s)", part, qty)
            messagebox.showwarning("Over scan", "Quantity exceeds expected")
            self._alert_beep()
            self.scan_var.set("")
            self.qty_var.set(1)
            return

        for ln in matching:
            self._update_line_widgets(ln)

        self._update_alloc_labels(allocations)

        self._update_last_entry(part, qty, allocations)

        self._insert_event(part, qty, raw)
        self.refresh_progress_table()
        self.scan_var.set("")
        self.qty_var.set(1)

        if all(line.remaining() == 0 for line in self.lines):
            self.dm.mark_waybill_terminated(self.waybill_var.get(), self.user_id)
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
    if not app.waybills:
        return
    try:
        app.mainloop()
    finally:
        if getattr(app, "session_id", None):
            app.record_partial_summary()
