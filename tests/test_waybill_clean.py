import pandas as pd

from src.logic.waybill_import import _clean_dataframe


def test_clean_dataframe_trims_and_converts():
    df = pd.DataFrame({
        "ITEM": [" P1 ", "P2"],
        "DESCRIPTION": [" Desc1 ", "Desc2"],
        "SHP QTY": [" 5 ", "foo"],
        "SUBINV": [" DRV-AMO ", " DRV-RM "],
        "Locator": [None, " B2 "],
        "Waybill": [" WB1 ", " WB1 "],
        "ITEM_COSTS": ["1 234,56", " 2,00 "],
        "SHIP_DATE": ["2024-01-01", "invalid"],
    })

    clean = _clean_dataframe(df)

    assert list(clean["ITEM"]) == ["P1", "P2"]
    assert list(clean["DESCRIPTION"]) == ["Desc1", "Desc2"]
    assert list(clean["SHP QTY"]) == [5, 0]
    assert list(clean["SUBINV"]) == ["DRV-AMO", "DRV-RM"]
    assert list(clean["Locator"]) == ["", "B2"]
    assert list(clean["Waybill"]) == ["WB1", "WB1"]
    assert list(clean["ITEM_COSTS"]) == [1234.56, 2.0]
    assert list(clean["SHIP_DATE"]) == ["2024-01-01", ""]
