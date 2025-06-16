import sqlite3

from src.data_manager import DataManager
from src.logic.scanning import ScannerLogic


def setup_identifiers(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO part_identifiers (part_number, upc_code, qty, description)"
        " VALUES ('P1', 'UPC1', '5', '')"
    )
    conn.commit()
    conn.close()


# DataManager.resolve_part ----------------------------------------------------

def test_resolve_part_direct(temp_db):
    setup_identifiers(temp_db)
    dm = DataManager(temp_db)
    part, qty = dm.resolve_part('P1')
    assert (part, qty) == ('P1', 5)


def test_resolve_part_upc(temp_db):
    setup_identifiers(temp_db)
    dm = DataManager(temp_db)
    part, qty = dm.resolve_part('UPC1')
    assert (part, qty) == ('P1', 5)


def test_resolve_part_case_insensitive(temp_db):
    setup_identifiers(temp_db)
    dm = DataManager(temp_db)
    part, qty = dm.resolve_part('p1')
    assert (part, qty) == ('P1', 5)


def test_resolve_part_upc_case_insensitive(temp_db):
    setup_identifiers(temp_db)
    dm = DataManager(temp_db)
    part, qty = dm.resolve_part('upc1')
    assert (part, qty) == ('P1', 5)


def test_resolve_part_missing(temp_db):
    setup_identifiers(temp_db)
    dm = DataManager(temp_db)
    part, qty = dm.resolve_part('UNKNOWN')
    assert (part, qty) == ('UNKNOWN', 1)


# ScannerLogic.resolve_part --------------------------------------------------

def test_scanner_resolve_from_csv(temp_db, tmp_path):
    dm = DataManager(temp_db)
    csv_path = tmp_path / 'ids.csv'
    csv_path.write_text(
        'part_number,upc_code,qty\nCSV_PART,CSV_UPC,3\n'
    )
    logic = ScannerLogic(dm, str(csv_path))
    part, qty = logic.resolve_part('CSV_UPC')
    assert (part, qty) == ('CSV_PART', 3)
