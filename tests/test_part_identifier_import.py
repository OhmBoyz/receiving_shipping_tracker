import sqlite3
from src.logic import part_identifier_import


def test_import_part_identifiers(temp_db, tmp_path):
    csv_path = tmp_path / "ids.csv"
    csv_content = (
        "part_number,upc_code,qty,description\n"
        "P1,UPC1,5,Desc1\n"
        "P2,UPC2,1,Desc2\n"
    )
    csv_path.write_text(csv_content)

    inserted = part_identifier_import.import_part_identifiers(str(csv_path), temp_db)
    assert inserted == 2

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT part_number, upc_code, qty, description FROM part_identifiers ORDER BY part_number"
    )
    rows = [(r[0], r[1], int(r[2]), r[3]) for r in cur.fetchall()]
    conn.close()
    assert rows == [("P1", "UPC1", 5, "Desc1"), ("P2", "UPC2", 1, "Desc2")]
