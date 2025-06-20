"""Logging configuration helpers for the application."""

from __future__ import annotations

import logging
import os
from pathlib import Path


LOG_FILE = Path(__file__).resolve().parent.parent / "tracker.log"


def setup_logging() -> None:
    """Configure :mod:`logging` to write messages to :data:`LOG_FILE`."""

    level = os.getenv("TRACKER_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    )

