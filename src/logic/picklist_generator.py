# src/logic/picklist_generator.py

from __future__ import annotations
import webbrowser
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import base64 # Add this import

def _get_logo_base64() -> str:
    """Reads the logo file and returns it as a Base64 encoded string for embedding."""
    logo_path = Path("eaton_logo.png") # Assumes eaton_logo.png is in the root project folder
    if not logo_path.is_file():
        return "" # Return empty string if logo not found
    try:
        with open(logo_path, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded_string}"
    except Exception:
        return "" # Return empty on error

# --- HTML and CSS for the picklist layout ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Shortage Job Report - {go_number}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header, .info-grid, .item-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        .header td {{ vertical-align: middle; }}
        .logo {{ width: 150px; }}
        .report-title {{ font-size: 24px; font-weight: bold; text-align: center; }}
        .info-grid td {{ border: 1px solid black; padding: 5px; }}
        .item-table th, .item-table td {{ border: 1px solid black; padding: 8px; text-align: left; vertical-align: top; }}
        .item-table th {{ background-color: #f2f2f2; font-weight: bold; }}
        .center {{ text-align: center; }}
        .stock-header {{ font-weight:bold; text-align:center; }}
        .stock-columns {{ text-align:center; }}
    </style>
</head>
<body>
    <table class="header">
        <tr>
            <td><img src="{logo_base64}" alt="Logo" class="logo"></td>
            <td class="report-title">SHORTAGE JOB REPORT</td>
        </tr>
    </table>

    <table class="info-grid">
        <tr>
            <td><strong>GO:</strong> {go_number}</td>
            <td><strong>ORACLE:</strong> {oracle_number}</td>
        </tr>
        <tr>
            <td><strong>CUSTOMER:</strong> {customer}</td>
            <td><strong>CUSTOMER JOB:</strong> {customer_job}</td>
        </tr>
    </table>
    
    <p><strong>PRINTED ON: {print_date}</strong></p>

    <table class="item-table">
        <thead>
            <tr>
                <th rowspan="2">ORACLE STATUS</th>
                <th rowspan="2">ITEM #</th>
                <th rowspan="2">DISCRETE JOB</th>
                <th rowspan="2">PART #</th>
                <th rowspan="2">OPEN QTY</th>
                <th rowspan="2">RCVD QTY</th>
                <th colspan="2">AMO</th>
                <th colspan="2">KB</th>
                <th colspan="2">SURPLUS</th>
                <th rowspan="2">DATE OF PICKING</th>
                <th rowspan="2">INITIALS</th>
            </tr>
            <tr>
                <th class="stock-header">PICKED</th><th class="stock-header">STOCK</th>
                <th class="stock-header">PICKED</th><th class="stock-header">STOCK</th>
                <th class="stock-header">PICKED</th><th class="stock-header">STOCK</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
</body>
</html>
"""

TABLE_ROW_TEMPLATE = """
<tr>
    <td>{flow_status}</td>
    <td>{item_number}</td>
    <td>{discrete_job}</td>
    <td>{part_number}</td>
    <td class="center">{qty_req}</td>
    <td class="center"><strong>{qty_fulfilled}</strong></td>
    <td class="stock-columns"></td><td class="stock-columns">{amo_stock_qty}</td>
    <td class="stock-columns"></td><td class="stock-columns">{kanban_stock_qty}</td>
    <td class="stock-columns"></td><td class="stock-columns">{surplus_stock_qty}</td>
    <td></td>
    <td></td>
</tr>
"""

def create_picklist_html(picklist_data: List[Dict]) -> str:
    """Generates the HTML content for a picklist."""
    if not picklist_data:
        return "<h1>No data available for this picklist.</h1>"

    # Assume header info is the same for all lines of a GO
    header_info = picklist_data[0]
    go_number = header_info.get("go_item", "").split('-')[0]

    table_rows_html = ""
    for row_data in picklist_data:
        # Calculate remaining qty to show as "OPEN QTY"
        open_qty = row_data.get("qty_req", 0) - row_data.get("qty_fulfilled", 0)
        table_rows_html += TABLE_ROW_TEMPLATE.format(
            flow_status=row_data.get("flow_status", ""),
            item_number=row_data.get("item_number", ""),
            discrete_job=row_data.get("discrete_job", ""),
            part_number=row_data.get("part_number", ""),
            qty_req=open_qty,
            qty_fulfilled=row_data.get("qty_fulfilled", 0),
            amo_stock_qty=row_data.get("amo_stock_qty", 0),
            kanban_stock_qty=row_data.get("kanban_stock_qty", 0),
            surplus_stock_qty=row_data.get("surplus_stock_qty", 0),
        )

    logo_base64_string = _get_logo_base64()

    return HTML_TEMPLATE.format(
        logo_base64=logo_base64_string, # Add this to the format call
        go_number=go_number,
        oracle_number=header_info.get("oracle", ""),
        customer="",  # Add if available
        customer_job="",  # Add if available
        print_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        table_rows=table_rows_html,
    )

def preview_picklist(html_content: str) -> None:
    """Saves HTML to a temp file and opens it in a web browser for preview."""
    # We will create a temp sub-directory to keep things clean
    temp_dir = Path(__file__).resolve().parent.parent / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    filepath = temp_dir / "picklist_preview.html"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    webbrowser.open(f"file://{filepath.resolve()}")