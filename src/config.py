# src/config.py
"""Configuration options for the application."""

import os

DB_PATH = "receiving_tracker.db"

# Allow users to control the CustomTkinter theme ("light" or "dark").
APPEARANCE_MODE = os.getenv("APPEARANCE_MODE", "light")

# --- NEW PRINTER CONFIGURATION ---
# Set the default printer name for the shipper's local (USB) printer
SHIPPER_PRINTER = "Prt05" # Example: Replace with your actual USB printer name

# Set the default printer name for the admin's office (network) printer
# This might be a UNC path like \\server\printer_name
ADMIN_PRINTER = "\\lacpqsrv01\LACPQPRT01" # type: ignore # Example: Replace with your actual network printer name