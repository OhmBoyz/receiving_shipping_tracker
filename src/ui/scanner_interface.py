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
        self.active_waybill: Optional[str] = None # Will hold the currently loaded waybill

        self.title("Shipper Interface")
        self.geometry("1200x700")
        if hasattr(self, "state"):
            try:
                self.state("zoomed")
            except Exception:
                pass
        ctk.set_appearance_mode(APPEARANCE_MODE)
        
        self.font_main_title = ctk.CTkFont(size=26, weight="bold")
        self.font_sidebar_title = ctk.CTkFont(size=40, weight="bold")
        self.font_sidebar_history = ctk.CTkFont(size=18)
        self.font_table_header = ctk.CTkFont(size=20, weight="bold")
        self.font_table_cell = ctk.CTkFont(size=18)
        self.font_controls = ctk.CTkFont(size=16)

        # --- Data Loading ---
        today = datetime.now().date()
        all_wbs = self._fetch_waybills(None)
        import_dates = self.dm.get_waybill_import_dates()
        
        self.today_waybills = []
        for wb in all_wbs:
            date_str = import_dates.get(wb)
            try:
                imp = datetime.fromisoformat(date_str).date() if date_str else None
            except Exception:
                imp = None
            if imp == today:
                self.today_waybills.append(wb)
        
        self.other_waybills = [
            wb for wb in self.dm.fetch_incomplete_waybills() 
            if wb not in self.today_waybills
        ]
        
        # --- NEW: Independent variables for each dropdown ---
        self.today_var = ctk.StringVar()
        self.other_var = ctk.StringVar()
        
        # --- Main Window Layout Configuration ---
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(3, weight=1)

        # --- Top Frame for Waybill Selection and Buttons ---
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        top_frame.columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(top_frame, text="Today's Waybills:", font=self.font_controls).grid(row=0, column=0, sticky="e", padx=(10, 5), pady=5)
        self.today_menu = ctk.CTkOptionMenu(
            top_frame, 
            values=["---"] + self.today_waybills, 
            variable=self.today_var, 
            command=self._on_waybill_select, 
            font=self.font_controls
        )
        self.today_menu.grid(row=0, column=1, sticky="ew", pady=5)

        ctk.CTkLabel(top_frame, text="Older/Incomplete:", font=self.font_controls).grid(row=0, column=2, sticky="e", padx=(10, 5), pady=5)
        self.other_menu = ctk.CTkOptionMenu(
            top_frame, 
            values=["---"] + self.other_waybills, 
            variable=self.other_var, 
            command=self._on_waybill_select, 
            font=self.font_controls
        )
        self.other_menu.grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=5)

        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        button_frame.columnconfigure((0, 1), weight=1)

        ctk.CTkButton(button_frame, text="Show All Today's Waybills", command=self._load_all_today, font=self.font_controls).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(button_frame, text="Show All Incomplete Waybills", command=self._load_all_incomplete, font=self.font_controls).grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.list_status = ctk.CTkLabel(self, text="", font=self.font_main_title)
        self.list_status.grid(row=2, column=0, columnspan=2, pady=(5, 0), padx=10, sticky="w")

        # --- Main Content Frame ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=2)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.lines_frame = ctk.CTkFrame(self.main_frame)
        self.lines_frame.grid(row=0, column=0, sticky="nsew")

        self.sidebar_frame = ctk.CTkFrame(self.main_frame)
        self.sidebar_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.sidebar_frame.columnconfigure(0, weight=1)
        self.sidebar_frame.rowconfigure(2, weight=1)

        # --- Sidebar Widgets ---
        self.progress_frame = ctk.CTkFrame(self.sidebar_frame)
        self.progress_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.alloc_frame = ctk.CTkFrame(self.sidebar_frame)
        self.alloc_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.amo_label = ctk.CTkLabel(self.alloc_frame, text="AMO", height=80, font=self.font_sidebar_title, fg_color="gray80", corner_radius=8)
        self.amo_label.pack(pady=5, fill="x", expand=True)
        self.amo_label._base_text = "AMO"
        self.kanban_label = ctk.CTkLabel(self.alloc_frame, text="KANBAN", height=80, font=self.font_sidebar_title, fg_color="gray80", corner_radius=8)
        self.kanban_label.pack(pady=5, fill="x", expand=True)
        self.kanban_label._base_text = "KANBAN"
        self._label_bg = self.amo_label.cget("fg_color")
        self.last_entries: List[str] = []
        self.history_box = ctk.CTkTextbox(self.sidebar_frame, font=self.font_sidebar_history)
        self.history_box.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
        self.history_box.configure(state="disabled")

        # --- Bottom Controls ---
        controls = ctk.CTkFrame(self)
        controls.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        controls.columnconfigure(2, weight=1)
        ctk.CTkLabel(controls, text="Qty:", font=self.font_controls).grid(row=0, column=0, padx=(0,5))
        self.qty_var = ctk.IntVar(value=1)
        self.qty_entry = ctk.CTkEntry(controls, textvariable=self.qty_var, width=60, font=self.font_controls)
        self.qty_entry.grid(row=0, column=1, padx=(0, 20))
        self.scan_var = ctk.StringVar()
        self.scan_entry = ctk.CTkEntry(controls, textvariable=self.scan_var, font=self.font_controls)
        self.scan_entry.grid(row=0, column=2, sticky="ew")
        self.scan_entry.bind("<Return>", self.process_scan)
        finish_btn = ctk.CTkButton(controls, text="Finish Waybill", command=self.manual_finish, font=self.font_controls)
        finish_btn.grid(row=0, column=3, padx=(20, 0))
        logout_btn = ctk.CTkButton(controls, text="End Session", command=self.manual_logout, font=self.font_controls)
        logout_btn.grid(row=0, column=4, padx=(10, 0))

        # --- Initial Load ---
        self.lines: List[Line] = []
        # Set initial state for dropdowns
        default_wb = self.today_waybills[0] if self.today_waybills else None
        if default_wb:
            self.today_var.set(default_wb)
            self.other_var.set("---")
            self.load_waybill(default_wb)
        else:
            self.today_var.set("---")
            self.other_var.set("---")
            self.list_status.configure(text="No Waybills Loaded")

        self.refresh_progress_table()
        try:
            self.protocol("WM_DELETE_WINDOW", self.manual_logout)
        except Exception:
            pass

    # --- NEW: Unified command for waybill selection ---
    def _on_waybill_select(self, selection: str):
        """Called when a user selects a waybill from EITHER dropdown."""
        if selection == "---":
            return

        # Deselect the other dropdown to avoid confusion
        if selection in self.today_waybills:
            self.other_var.set("---")
        elif selection in self.other_waybills:
            self.today_var.set("---")
        
        self.load_waybill(selection)

    def _load_list(self, waybills: List[str], label: str) -> None:
        """Loads a list of waybills for a multi-waybill view."""
        self.list_status.configure(text=label)
        # Deselect both individual waybill dropdowns
        self.today_var.set("---")
        self.other_var.set("---")

        if not waybills:
            for widget in self.lines_frame.winfo_children():
                widget.destroy()
            self.lines = []
            return
        
        self.active_waybill = waybills[0]
        self._load_waybills_data(waybills)

    def _load_all_today(self) -> None:
        self._load_list(self.today_waybills, "Today's Waybills")

    def _load_all_incomplete(self) -> None:
        self._load_list(self.other_waybills, "Incomplete & Older Waybills")

    def load_waybill(self, waybill: str) -> None:
        """Loads a single waybill view."""
        if not waybill: return
        self.active_waybill = waybill
        self.list_status.configure(text=f"Showing Single Waybill: {waybill}")
        self._load_waybills_data([waybill])

    def _load_waybills_data(self, waybills: List[str]) -> None:
        # This method's internal logic is mostly unchanged
        if not waybills:
            for widget in self.lines_frame.winfo_children():
                widget.destroy()
            self.lines = []
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

        self.lines_frame.columnconfigure(0, weight=1)
        headers_frame = ctk.CTkFrame(self.lines_frame, fg_color="transparent")
        headers_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5,0))
        
        headers_frame.columnconfigure(0, minsize=220)
        headers_frame.columnconfigure(1, minsize=90)
        headers_frame.columnconfigure(2, weight=1)
        headers_frame.columnconfigure(3, minsize=90)
        
        ctk.CTkLabel(headers_frame, text="Part", font=self.font_table_header, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(headers_frame, text="Total", font=self.font_table_header, anchor="w").grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(headers_frame, text="Progress", font=self.font_table_header, anchor="w").grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(headers_frame, text="Remaining", font=self.font_table_header, anchor="w").grid(row=0, column=3, sticky="w")

        scrollable_frame = ctk.CTkScrollableFrame(self.lines_frame, fg_color="transparent")
        scrollable_frame.grid(row=1, column=0, sticky="nsew")
        self.lines_frame.rowconfigure(1, weight=1)
        scrollable_frame.columnconfigure(0, weight=1)

        for i, (part, lines) in enumerate(part_groups.items()):
            row_frame = ctk.CTkFrame(scrollable_frame)
            row_frame.grid(row=i, column=0, sticky="ew", pady=2)
            
            row_frame.columnconfigure(0, minsize=220)
            row_frame.columnconfigure(1, minsize=90)
            row_frame.columnconfigure(2, weight=1)
            row_frame.columnconfigure(3, minsize=90)

            ctk.CTkLabel(row_frame, text=part, anchor="w", font=self.font_table_cell).grid(row=0, column=0, sticky="w", padx=5)
            total_qty = sum(l.qty_total for l in lines)
            ctk.CTkLabel(row_frame, text=str(total_qty), font=self.font_table_cell).grid(row=0, column=1)

            pb = ctk.CTkProgressBar(row_frame)
            pb.grid(row=0, column=2, sticky="ew", padx=5)
            rem_label = ctk.CTkLabel(row_frame, font=self.font_table_cell)
            rem_label.grid(row=0, column=3, padx=10)

            for ln in lines:
                ln.progress = pb
                ln.rem_label = rem_label
            self._update_line_widgets(lines[0])

        self.refresh_progress_table()
        self.scan_entry.focus_set()

    def refresh_progress_table(self) -> None:
        # This method's internal logic is mostly unchanged
        for widget in self.progress_frame.winfo_children():
            widget.destroy()

        self.progress_frame.columnconfigure(3, weight=1)
        header_font = ctk.CTkFont(size=16, weight="bold")
        cell_font = ctk.CTkFont(size=14)

        for idx, (text, width, sticky) in enumerate([
            ("Waybill", 120, "w"), ("Total", 60, "w"), ("Rem", 60, "w"), ("Progress", 150, "ew")
        ]):
            lbl = ctk.CTkLabel(self.progress_frame, text=text, font=header_font)
            lbl.grid(row=0, column=idx, sticky=sticky)
        
        rows = self._get_waybill_progress()
        dates = self.dm.get_waybill_import_dates()
        today = datetime.now().date()
        for row_idx, (waybill, total, remaining) in enumerate(rows, start=1):
            date_str = dates.get(waybill, "")
            try:
                parsed = datetime.fromisoformat(date_str).date() if date_str else None
            except Exception:
                parsed = None
            color = "orange" if parsed and parsed < today and remaining > 0 else None
            
            lbl_text = f"{waybill} ({parsed.strftime('%Y-%m-%d') if parsed else 'N/A'})"
            kwargs = dict(text=lbl_text, anchor="w", font=cell_font)
            if color:
                kwargs["text_color"] = color
            ctk.CTkLabel(self.progress_frame, **kwargs).grid(row=row_idx, column=0, sticky="w", pady=1)
            ctk.CTkLabel(self.progress_frame, text=str(total), font=cell_font).grid(row=row_idx, column=1, sticky="w")
            ctk.CTkLabel(self.progress_frame, text=str(remaining), font=cell_font).grid(row=row_idx, column=2, sticky="w")
            
            pb = ctk.CTkProgressBar(self.progress_frame)
            pb.grid(row=row_idx, column=3, sticky="ew", padx=5)
            ratio = (total - remaining) / total if total else 0
            pb.set(ratio)
            pb.configure(progress_color=_color_from_ratio(ratio))

    def _get_session(self, waybill: str) -> int:
        return self.dm.create_session(self.user_id, waybill)

    def _fetch_waybills(self, date: str | None = None) -> List[str]:
        return self.dm.fetch_waybills(date)
    
    def _fetch_scans(self, waybill: str) -> Dict[str, int]:
        return self.dm.fetch_scans(waybill)
    
    def _get_waybill_progress(self) -> List[tuple[str, int, int]]:
        return self.dm.get_waybill_progress()

    def load_bo_report(self, filepath: str) -> None:
        try:
            self.bo_df = bo_report.load_bo_excel(filepath)
        except NotImplementedError:
            self.bo_df = None
        except Exception as exc:
            messagebox.showerror("BO load error", str(exc))

    def _insert_event(self, part: str, qty: int, raw: str) -> None:
        if self.session_id is not None:
            self.dm.insert_scan_event(self.session_id, self.active_waybill, part, qty, raw_scan=raw)

    def _update_session_waybill(self, waybill: str) -> None:
        if self.session_id is not None:
            self.dm.update_session_waybill(self.session_id, waybill)

    def _finish_session(self) -> None:
        self.record_partial_summary()
        self.destroy()

    def manual_finish(self) -> None:
        if messagebox.askyesno("Confirm", "Finish current waybill and End Session?"):
            self._finish_session()

    def manual_logout(self) -> None:
        if messagebox.askyesno("Confirm", "End scanning session and exit?"):
            self._finish_session()

    def _record_summary(self) -> None:
        scans = self._fetch_scans(self.active_waybill)
        rows = []
        for part, total in scans.items():
            expected = sum(line.qty_total for line in self.lines if line.part == part)
            remaining = expected - total
            allocated = ", ".join(f"{line.subinv}:{line.scanned}" for line in self.lines if line.part == part)
            rows.append((self.session_id, self.active_waybill, self.user_id, part, total, expected, remaining, allocated, datetime.now().date().isoformat()))
        if rows:
            self.dm.insert_scan_summaries(rows)

    def record_partial_summary(self) -> None:
        if self.session_id is None or self._summary_recorded:
            return
        if self.active_waybill:
            self._record_summary()
        self.dm.end_session(self.session_id)
        self.session_id = None
        self._summary_recorded = True

    def _update_line_widgets(self, line: Line) -> None:
        group = [ln for ln in self.lines if ln.part == line.part]
        total_qty = sum(l.qty_total for l in group)
        total_scanned = sum(l.scanned for l in group)
        ratio = total_scanned / total_qty if total_qty else 0
        if hasattr(line, 'progress') and line.progress is not None:
            line.progress.set(ratio)
            line.progress.configure(progress_color=_color_from_ratio(ratio))
        if hasattr(line, 'rem_label') and line.rem_label is not None:
            line.rem_label.configure(text=str(total_qty - total_scanned))

    def _flash_alloc_label(self, label: ctk.CTkLabel, qty: int, color) -> None:
        label.configure(text=f"{label._base_text} +{qty}", fg_color=color)
        if getattr(label, "_after_id", None):
            self.after_cancel(label._after_id)
        label._after_id = self.after(1500, lambda: label.configure(text=label._base_text, fg_color=self._label_bg))

    def _update_alloc_labels(self, allocations: Dict[str, int]) -> None:
        if allocations.get("AMO"):
            self._flash_alloc_label(self.amo_label, allocations["AMO"], "red")
        if allocations.get("KANBAN"):
            self._flash_alloc_label(self.kanban_label, allocations["KANBAN"], "green")

    def _alert_beep(self) -> None:
        self.bell()
        if platform.system() == "Windows":
            try:
                import winsound
                winsound.Beep(1000, 200)
            except Exception:
                pass



    def _update_last_entry(self, part: str, qty: int, allocations: Dict[str, int]) -> None:
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
        self.history_box.insert("end", "\n".join(reversed(self.last_entries)))
        self.history_box.configure(state="disabled")

    def process_scan(self, event=None) -> None:
        raw = self.scan_var.get().strip()
        if not raw: return
        try:
            qty = self.qty_var.get()
        except Exception:
            qty = 1
        if qty <= 0:
            messagebox.showwarning("Invalid qty", "Quantity must be > 0")
            self._alert_beep()
            return
        part, box_qty = self.logic.resolve_part(raw)
        part = part.upper()
        if qty == 1 and box_qty > 1:
            qty = box_qty
        if self.bo_df is not None:
            try:
                bo_report.find_bo_match(part, self.bo_df)
            except NotImplementedError:
                pass

        matching = [ln for ln in self.lines if ln.part == part]
        if not matching:
            messagebox.showwarning("Unknown part", f"{part} not on active waybill list.")
            self._alert_beep()
            self.scan_var.set("")
            self.qty_var.set(1)
            return

        try:
            allocations = self.logic.allocate(matching, qty)
        except ValueError:
            logger.warning("Over scan detected for part %s (qty=%s)", part, qty)
            messagebox.showwarning("Over scan", "Quantity exceeds expected total for this part.")
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
            self.dm.mark_waybill_terminated(self.active_waybill, self.user_id)
            all_done_progress = self._get_waybill_progress()
            if all(rem == 0 for _, _, rem in all_done_progress):
                if messagebox.askyesno("All Waybills Complete", "All waybills finished. Close interface?"):
                    self._finish_session()
            else:
                messagebox.showinfo("Waybill Finished", "Current waybill completed. Select another or show all.")


def start_shipper_interface(
    user_id: int,
    db_path: str = DB_PATH,
    csv_path: str = PART_IDENTIFIERS_CSV,
) -> None:
    """Launch the shipper interface for ``user_id``."""
    app = ShipperWindow(user_id, db_path, csv_path)
    if not (app.today_waybills or app.other_waybills):
        return
    try:
        app.mainloop()
    finally:
        if getattr(app, "session_id", None):
            app.record_partial_summary()