# src/ui/picklist_update_interface.py

from __future__ import annotations
import customtkinter as ctk
from tkinter import messagebox
from typing import Dict, List

from src.data_manager import DataManager

class PicklistUpdateWindow(ctk.CTkToplevel):
    def __init__(self, parent, dm: DataManager):
        super().__init__(parent)
        self.dm = dm
        self.title("Update Warehouse Pick")
        self.geometry("700x500")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Top frame for input ---
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(top_frame, text="Enter GO Number:").pack(side="left", padx=(10, 5))
        self.go_entry = ctk.CTkEntry(top_frame)
        self.go_entry.pack(side="left", fill="x", expand=True)
        self.go_entry.bind("<Return>", self._load_picklist_lines)
        
        load_btn = ctk.CTkButton(top_frame, text="Load Picklist", command=self._load_picklist_lines)
        load_btn.pack(side="left", padx=5)

        # --- Scrollable frame for picklist lines ---
        self.lines_frame = ctk.CTkScrollableFrame(self, label_text="Picklist Lines (In Progress)")
        self.lines_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.lines_frame.grid_columnconfigure(2, weight=1)

        # --- Bottom frame for submission ---
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.submit_btn = ctk.CTkButton(
            bottom_frame,
            text="Submit Picked Quantities",
            command=self._submit_updates,
            state="disabled"
        )
        self.submit_btn.pack(pady=5)
        
        self.entry_widgets: Dict[int, ctk.StringVar] = {}

    def _load_picklist_lines(self, event=None):
        go_number = self.go_entry.get().strip().upper()
        if not go_number:
            messagebox.showwarning("Input Required", "Please enter a GO Number.")
            return

        for widget in self.lines_frame.winfo_children():
            widget.destroy()
        self.entry_widgets.clear()

        lines = self.dm.get_inprogress_lines_for_go(go_number)
        
        if not lines:
            messagebox.showinfo("Not Found", f"No 'IN_PROGRESS' picklist found for GO Number: {go_number}")
            self.submit_btn.configure(state="disabled")
            return
            
        # Create headers
        header_frame = ctk.CTkFrame(self.lines_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header_frame, text="Part Number", anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header_frame, text="Qty Remaining").grid(row=0, column=1, padx=10)
        ctk.CTkLabel(header_frame, text="Qty Picked").grid(row=0, column=2, padx=10)

        for i, line in enumerate(lines, start=1):
            qty_remaining = line['qty_req'] - line['qty_fulfilled']
            
            row_frame = ctk.CTkFrame(self.lines_frame)
            row_frame.grid(row=i, column=0, sticky="ew", pady=2, padx=5)
            row_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row_frame, text=line['part_number'], anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(row_frame, text=str(qty_remaining)).grid(row=0, column=1, padx=10)
            
            entry_var = ctk.StringVar()
            entry = ctk.CTkEntry(row_frame, textvariable=entry_var, width=80)
            entry.grid(row=0, column=2, padx=10)
            self.entry_widgets[line['id']] = entry_var
        
        self.submit_btn.configure(state="normal")

    def _submit_updates(self):
        updates: List[tuple[int, int]] = []
        for bo_id, entry_var in self.entry_widgets.items():
            qty_str = entry_var.get().strip()
            if qty_str:
                try:
                    picked_qty = int(qty_str)
                    if picked_qty > 0:
                        updates.append((bo_id, picked_qty))
                except ValueError:
                    messagebox.showerror("Invalid Input", f"Please enter a valid number for all picked quantities.")
                    return
        
        if not updates:
            messagebox.showinfo("No Input", "No new picked quantities were entered.")
            return

        if messagebox.askyesno("Confirm", "Are you sure you want to submit these picked quantities? This cannot be undone."):
            self.dm.batch_update_bo_fulfillment(updates)
            messagebox.showinfo("Success", "Picklist quantities have been updated successfully.")
            self.destroy() # Close the window after submission