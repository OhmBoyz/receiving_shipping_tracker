import sqlite3
import pytest


def setup_waybill(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO waybill_lines (waybill_number, part_number, qty_total, subinv, locator, description, item_cost, date)"
        " VALUES ('WB1', 'P1', 5, 'DRV-AMO', '', '', 0, '2024-01-01')"
    )
    conn.commit()
    conn.close()


def test_partial_summary_written_on_exception(temp_db, monkeypatch):
    setup_waybill(temp_db)

    from src.ui import scanner_interface

    def boom(self):
        self.qty_var.set(2)
        self.scan_var.set('P1')
        self.process_scan()
        raise RuntimeError('boom')

    monkeypatch.setattr(
        scanner_interface.ShipperWindow,
        'mainloop',
        boom,
        raising=False,
    )

    with pytest.raises(RuntimeError):
        scanner_interface.start_shipper_interface(1, temp_db)

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute('SELECT total_scanned FROM scan_summary')
    result = cur.fetchone()
    cur.execute('SELECT end_time FROM scan_sessions')
    end = cur.fetchone()[0]
    conn.close()

    assert result == (2,)
    assert end is not None
