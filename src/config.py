# src/config.py
"""Configuration options for the application."""

import os

DB_PATH = "receiving_tracker.db"

# Allow users to control the CustomTkinter theme ("light" or "dark").
APPEARANCE_MODE = os.getenv("APPEARANCE_MODE", "light")

