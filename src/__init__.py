"""Package initialization and logging configuration."""

from __future__ import annotations

from .logging_utils import setup_logging

# Configure logging on package import
setup_logging()
