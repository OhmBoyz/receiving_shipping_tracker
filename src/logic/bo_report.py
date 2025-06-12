"""Utilities for working with the BO Excel report.

This module will eventually parse the BO report and help allocate scanned
parts to backorders. Currently it only defines placeholder functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def load_bo_excel(filepath: str | Path) -> pd.DataFrame:
    """Load the BO Excel file and return a DataFrame.

    Parameters
    ----------
    filepath:
        Path to the BO report file.

    Returns
    -------
    pandas.DataFrame
        The parsed BO data.
    """
    raise NotImplementedError("BO report parsing not implemented yet")


def find_bo_match(part_number: str, bo_df: pd.DataFrame) -> Optional[pd.Series]:
    """Return the BO row matching ``part_number`` if present.

    Parameters
    ----------
    part_number:
        Part number being scanned.
    bo_df:
        DataFrame returned by :func:`load_bo_excel`.

    Returns
    -------
    Optional[pandas.Series]
        The matching row or ``None``.
    """
    raise NotImplementedError("BO matching not implemented yet")

