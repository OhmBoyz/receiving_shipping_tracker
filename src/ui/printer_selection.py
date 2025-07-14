# src/ui/printer_selection.py

import customtkinter as ctk
from typing import List, Optional

class PrinterSelectDialog(ctk.CTkToplevel):
    def __init__(self, parent, printer_list: List[str]):
        super().__init__(parent)
        self.title("Select Printer")
        self.geometry("400x150")
        
        self.label = ctk.CTkLabel(self, text="Please select a printer:")
        self.label.pack(padx=20, pady=10)
        
        self.printer_var = ctk.StringVar(value=printer_list[0] if printer_list else "")
        self.printer_menu = ctk.CTkOptionMenu(self, variable=self.printer_var, values=printer_list)
        self.printer_menu.pack(padx=20, pady=5)
        
        self.print_button = ctk.CTkButton(self, text="Print", command=self._on_print)
        self.print_button.pack(padx=20, pady=20)
        
        self.selected_printer: Optional[str] = None
        self.grab_set() # Keep this window on top
        self.wait_window() # Wait until this window is closed

    def _on_print(self):
        self.selected_printer = self.printer_var.get()
        self.destroy()