"""Shipper scanning interface."""

from __future__ import annotations

import logging
import json

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

import pandas as pd
import platform

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from src.logic import bo_report

from src.config import DB_PATH, APPEARANCE_MODE
from src.data_manager import DataManager
from src.logic.scanning import Line, ScannerLogic

from src.config import SHIPPER_PRINTER

from src.logic import picklist_generator

from src.ui.picklist_update_interface import PicklistUpdateWindow

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
        self.affected_go_items = set()
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
        self.bo_label = ctk.CTkLabel(self.alloc_frame, text="BACK ORDER", height=80, font=self.font_sidebar_title, fg_color="gray80", corner_radius=8)
        self.bo_label.pack(pady=5, fill="x", expand=True)
        self.bo_label._base_text = "BACK ORDER"
        
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
        self.scan_entry.bind("<KeyRelease>", self._show_suggestions)
        self.suggestion_win = None
        self.suggestion_list = None
        update_pick_btn = ctk.CTkButton(
            controls, 
            text="Update Warehouse Pick", 
            command=self._open_picklist_updater,
            font=self.font_controls
        )
        update_pick_btn.grid(row=0, column=5, padx=(20, 0))
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
            line = Line(row[0], row[1].upper(), int(row[2]), friendly, row[4], code)
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
        """Called by the 'Finish Waybill' button."""
        if messagebox.askyesno("Confirm", "Finish current waybill and End Session?"):
            # Mark the specific waybill as finished if one is active
            if self.active_waybill:
                self.dm.mark_waybill_terminated(self.active_waybill, self.user_id)
            self._finish_session()

    def manual_logout(self) -> None:
        """Called by the 'End Session' button or closing the window."""
        # Check if any work was done before showing the confirmation
        if self.session_id and not self._summary_recorded:
            if messagebox.askyesno("Confirm", "End scanning session and exit?"):
                self._finish_session()
        else:
            # If no work was done, just close
            self.destroy()

    def _record_summary(self) -> None:
        if self.session_id is None:
            return

        waybills = {line.waybill_number for line in self.lines}
        rows = []

        # Get the accurate, aggregated allocation strings for the entire session
        session_allocations = self.dm.get_session_allocations(self.session_id)

        for wb in waybills:
            scans = self._fetch_scans(wb) # Gets total quantities per part
            for part, total in scans.items():
                expected = sum(
                    ln.qty_total for ln in self.lines if ln.part == part and ln.waybill_number == wb
                )
                remaining = expected - total

                # Use the accurate allocation string we fetched
                allocated_str = session_allocations.get(part, "")

                rows.append(
                    (
                        self.session_id,
                        wb,
                        self.user_id,
                        part,
                        total,
                        expected,
                        remaining,
                        allocated_str, # Use the correct string here
                        datetime.now().date().isoformat(),
                    )
                )
        if rows:
            self.dm.insert_scan_summaries(rows)

    def record_partial_summary(self) -> None:
        if self.session_id is None or self._summary_recorded:
            return
        self._process_automated_picklists()
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

    def _reset_alloc_labels(self) -> None:
        for lbl in (self.amo_label, self.kanban_label, self.bo_label):
            lbl.configure(text=lbl._base_text, fg_color=self._label_bg)

    def _flash_alloc_label(self, label: ctk.CTkLabel, qty: int, color) -> None:
        label.configure(text=f"{label._base_text} +{qty}", fg_color=color)

    def _update_alloc_labels(self, allocations: Dict[str, int]) -> None:
        if allocations.get("AMO"):
            self._flash_alloc_label(self.amo_label, allocations["AMO"], "red")
        if allocations.get("KANBAN"):
            self._flash_alloc_label(self.kanban_label, allocations["KANBAN"], "green")
        if allocations.get("BACK ORDER"):
            self._flash_alloc_label(self.kanban_label, allocations["BACK ORDER"], "yellow")

    def _alert_beep(self) -> None:
        self.bell()
        if platform.system() == "Windows":
            try:
                import winsound
                winsound.Beep(1000, 200)
            except Exception:
                pass

    def _hide_suggestions(self) -> None:
        if self.suggestion_win is not None:
            try:
                self.suggestion_win.withdraw()
            except Exception:
                pass

    def _show_suggestions(self, event=None) -> None:
        text = self.scan_var.get().strip().upper()
        if not text:
            self._hide_suggestions()
            return
        parts = sorted({l.part for l in self.lines if l.part.startswith(text)})
        if not parts:
            self._hide_suggestions()
            return
        if self.suggestion_win is None:
            self.suggestion_win = tk.Toplevel(self)
            self.suggestion_win.overrideredirect(True)
            self.suggestion_list = tk.Listbox(self.suggestion_win)
            self.suggestion_list.pack(fill="both", expand=True)
            self.suggestion_list.bind("<Double-Button-1>", self._on_suggestion_select)
        else:
            self.suggestion_list.delete(0, tk.END)
        for part in parts:
            self.suggestion_list.insert(tk.END, part)
        x = self.scan_entry.winfo_rootx()
        y = self.scan_entry.winfo_rooty() + self.scan_entry.winfo_height()
        self.suggestion_win.geometry(f"+{x}+{y}")
        self.suggestion_win.deiconify()

    def _on_suggestion_select(self, event=None) -> None:
        if self.suggestion_list is None:
            return
        try:
            part = self.suggestion_list.get(tk.ACTIVE)
        except Exception:
            return
        self.scan_var.set(part)
        self._hide_suggestions()
        self.process_scan()



    def _update_last_entry(self, part: str, qty: int, allocations: Dict[str, int]) -> None:
        alloc_parts = []
        if allocations.get("AMO"):
            alloc_parts.append(f"AMO {allocations['AMO']}")
        if allocations.get("KANBAN"):
            alloc_parts.append(f"KANBAN {allocations['KANBAN']}")
        if allocations.get("BACK ORDER"):
            alloc_parts.append(f"BACK ORDER {allocations['BACK ORDER']}")
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
        self._reset_alloc_labels()
        self._hide_suggestions()
        raw = self.scan_var.get().strip()
        if not raw:
            return

        try:
            total_scanned_qty = self.qty_var.get()
        except Exception:
            total_scanned_qty = 1

        if total_scanned_qty <= 0:
            messagebox.showwarning("Invalid qty", "Quantity must be > 0")
            self._alert_beep()
            return

        part, box_qty = self.logic.resolve_part(raw)
        part = part.upper()
        if total_scanned_qty == 1 and box_qty > 1:
            total_scanned_qty = box_qty

        matching_lines = [ln for ln in self.lines if ln.part == part]
        if not matching_lines:
            messagebox.showwarning("Unknown part", f"{part} not on active waybill list.")
            self._alert_beep()
            self.scan_var.set("")
            self.qty_var.set(1)
            return

        # --- CORRECTED ALLOCATION LOGIC ---

        qty_remaining_from_scan = total_scanned_qty
        bo_allocations = {}
        
        # 1. Prioritize fulfilling Back Orders
        open_bo_lines = self.dm.get_open_bo_lines(part)
        if open_bo_lines:
            for bo_id, go_item, qty_req, qty_fulfilled in open_bo_lines:
                if qty_remaining_from_scan == 0:
                    break

                # Calculate the actual quantity still needed for this line
                qty_truly_needed = qty_req - qty_fulfilled
                if qty_truly_needed <= 0:
                    continue

                # Determine how much of the scan to apply to this BO line
                qty_for_this_bo = min(qty_remaining_from_scan, qty_truly_needed)

                self.dm.update_bo_fulfillment(bo_id, qty_for_this_bo)
                
                # Aggregate BO allocations for logging
                current_bo_total = bo_allocations.get("BACK ORDER", 0)
                bo_allocations["BACK ORDER"] = current_bo_total + qty_for_this_bo
                
                qty_remaining_from_scan -= qty_for_this_bo

            if bo_allocations.get("BACK ORDER", 0) > 0:
                total_bo_qty = bo_allocations["BACK ORDER"]
                messagebox.showinfo(
                    "Back Order Allocation",
                    f"{total_bo_qty} units of {part} have been allocated to open Back Orders.\n"
                    f"Please set them aside in the BO Staging Area."
                )
                self._flash_alloc_label(self.bo_label, total_bo_qty, "yellow")
                first_go_item = open_bo_lines[0][1] # e.g., 'CSVQ005405-002S1'
                go_number = first_go_item.split('-')[0]
                self.affected_go_items.add(go_number)

        # 2. Allocate the remaining quantity to the waybill (AMO/KANBAN)
        #    and update the total waybill progress with the original total.
        try:
            # First, update waybill progress with the FULL scanned quantity
            self.logic.allocate(matching_lines, total_scanned_qty)
            
            # Then, determine the destination (AMO/KANBAN) for the remainder
            if qty_remaining_from_scan > 0:
                 # This call is for display/logging purposes ONLY.
                 # We create a temporary, disconnected set of lines to calculate this.
                temp_lines = [Line(rowid=ln.rowid, part=ln.part, qty_total=ln.qty_total, subinv=ln.subinv, waybill_number=ln.waybill_number, scanned=ln.scanned - qty_remaining_from_scan) for ln in matching_lines]
                standard_allocations = self.logic.allocate(temp_lines, qty_remaining_from_scan)
            else:
                standard_allocations = {}

        except ValueError:
            messagebox.showwarning("Over scan", "Quantity exceeds expected total for this part on the waybill.")
            self._alert_beep()
            return
        
        # 3. Update UI and Log everything
        self._update_alloc_labels(standard_allocations)
        for ln in matching_lines:
            self._update_line_widgets(ln)

        combined_allocations = {**bo_allocations, **standard_allocations}
        self._update_last_entry(part, total_scanned_qty, combined_allocations)

        if self.session_id is not None:
            # Convert the dictionary to a JSON string for storage
            alloc_details_str = json.dumps(combined_allocations)
            self.dm.insert_scan_event(
                self.session_id,
                matching_lines[0].waybill_number,
                part,
                total_scanned_qty,
                raw_scan=raw,
                allocation_details=alloc_details_str # Pass the new data here
            )

        self.refresh_progress_table()
        self.scan_var.set("")
        self.qty_var.set(1)

        # 4. Check for waybill completion
        if all(line.remaining() == 0 for line in self.lines):
            self.dm.mark_waybill_terminated(self.active_waybill, self.user_id)
            all_done_progress = self._get_waybill_progress()
            if all(rem == 0 for _, _, rem in all_done_progress):
                if messagebox.askyesno("All Waybills Complete", "All waybills finished. Close interface?"):
                    self._finish_session()
            else:
                messagebox.showinfo("Waybill Finished", "Current waybill completed. Select another or show all.")
    
    def _process_automated_picklists(self) -> None:
        """
        Processes affected GO numbers at the end of a session to generate
        new or updated picklists automatically.
        """
        if not self.affected_go_items:
            return

        for go_number in self.affected_go_items:
            all_lines_for_go = self.dm.get_all_items_for_go(go_number)
            if not all_lines_for_go:
                continue

            status_set = {item['pick_status'] for item in all_lines_for_go}

            # Determine which scenario we are in
            is_updated_job = 'IN_PROGRESS' in status_set and 'NOT_STARTED' in status_set
            # A fresh job is one where no picklist has been started
            is_fresh_job = 'IN_PROGRESS' not in status_set

            if is_fresh_job or is_updated_job:
                # Generate the HTML. Add a title for updated picklists.
                html_content = picklist_generator.create_picklist_html(all_lines_for_go)
                if is_updated_job:
                    html_content = html_content.replace(
                        "<td class=\"report-title\">SHORTAGE JOB REPORT</td>",
                        "<td class=\"report-title\">** UPDATED **<br>SHORTAGE JOB REPORT</td>"
                    )

                # Generate PDF and send to the shipper's default printer
                pdf_path = picklist_generator.generate_picklist_pdf(html_content)
                picklist_generator.send_pdf_to_printer(pdf_path, SHIPPER_PRINTER)

                # Prepare lists of IDs for status updates
                ids_to_in_progress = []
                ids_to_completed = []

                for item in all_lines_for_go:
                    is_fulfilled = item['qty_fulfilled'] >= item['qty_req']
                    
                    if is_fulfilled and item['pick_status'] != 'COMPLETED':
                        ids_to_completed.append(item['id'])
                    elif not is_fulfilled and item['pick_status'] == 'NOT_STARTED':
                        ids_to_in_progress.append(item['id'])
                
                # Perform batch updates
                if ids_to_in_progress:
                    self.dm.update_bo_items_status(ids_to_in_progress, "IN_PROGRESS")
                if ids_to_completed:
                    self.dm.update_bo_items_status(ids_to_completed, "COMPLETED")

        # Clear the set for the next session
        self.affected_go_items.clear()
    
    def _open_picklist_updater(self):
        """Opens the toplevel window for updating warehouse picks."""
        updater = PicklistUpdateWindow(self, self.dm)
        updater.grab_set() # Keep the window on top


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