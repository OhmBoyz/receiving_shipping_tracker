# src/logic/picklist_generator.py

from __future__ import annotations
import webbrowser
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import base64
import os
import sys
import win32print
import win32api
from weasyprint import HTML

def _get_logo_base64() -> str:
    """Reads the logo file and returns it as a Base64 encoded string for embedding."""
    logo_path = Path("eaton_logo.png") # Assumes eaton_logo.png is in the root project folder
    if not logo_path.is_file():
        # Handle running from inside the PyInstaller temp folder
        if hasattr(sys, '_MEIPASS'):
            logo_path = Path(sys._MEIPASS) / "eaton_logo.png"

    if not logo_path.is_file():
        return "" # Return empty string if logo not found
    try:
        with open(logo_path, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded_string}"
    except Exception:
        return ""

# --- HTML Template is unchanged ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Shortage Job Report - {go_number}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header-container {{ position: relative; }}
        .header, .info-grid {{ width: 100%; border-collapse: collapse; }}
        .item-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .logo {{ width: 150px; }}
        .report-title {{ font-size: 24px; font-weight: bold; text-align: center; }}
        .info-grid td {{ border: 1px solid black; padding: 5px; }}
        .item-table th, .item-table td {{ border: 1px solid black; padding: 8px; text-align: center; vertical-align: top; }}
        .item-table th {{ background-color: #f2f2f2; font-weight: bold; }}
        .center {{ text-align: center; }}
        .stock-header {{ font-weight:bold; text-align:center; }}
        .stock-cell {{ background-color: #EAEAEA; font-weight: bold; text-align: center; }}

        @media print {{
            @page {{ size: landscape; }} /* Set print orientation to landscape */
            thead {{ display: table-header-group; }}
            body {{ margin-top: 200px; }}
            .header-container {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background-color: white;
                padding: 20px;
                border-bottom: 1px solid #ccc;
            }}
        }}
    </style>
</head>
<body>
    <div class="header-container">
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
    </div>
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
    <td class="center"></td><td class="stock-cell">{amo_stock_qty}</td>
    <td class="center"></td><td class="stock-cell">{kanban_stock_qty}</td>
    <td class="center"></td><td class="stock-cell">{surplus_stock_qty}</td>
    <td></td>
    <td></td>
</tr>
"""

def create_picklist_html(picklist_data: List[Dict]) -> str:
    """Generates the HTML content for a picklist."""
    if not picklist_data:
        return "<h1>No data available for this picklist.</h1>"

    header_info = picklist_data[0]
    go_number = header_info.get("go_item", "").split('-')[0]

    table_rows_html = ""
    for row_data in picklist_data:
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
        logo_base64=logo_base64_string,
        go_number=go_number,
        oracle_number=header_info.get("oracle", ""),
        customer="",
        customer_job="",
        print_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        table_rows=table_rows_html,
    )

def _get_temp_filepath(filename: str) -> Path:
    """Gets the correct temporary path, whether running as a script or a frozen exe."""
    if hasattr(sys, '_MEIPASS'):
        # We are running in a PyInstaller bundle, use its temp folder
        temp_dir = Path(sys._MEIPASS)
    else:
        # We are running in a normal Python environment
        temp_dir = Path("temp")
    
    temp_dir.mkdir(exist_ok=True)
    return temp_dir / filename

def preview_picklist(html_content: str) -> None:
    """Saves HTML to a temp file and opens it in a web browser for preview."""
    filepath = _get_temp_filepath("picklist_preview.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    webbrowser.open(f"file://{filepath.resolve()}")

def print_picklist(html_content: str) -> bool:
    """Saves HTML to a temp file and attempts to open the print dialog."""
    filepath = _get_temp_filepath("picklist_to_print.html")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        if sys.platform == "win32":
            os.startfile(str(filepath), "print")
        else:
            webbrowser.open(f"file://{filepath.resolve()}")
        return True
    except Exception as e:
        print(f"Error printing picklist: {e}")
        return False

def generate_picklist_pdf(html_content: str) -> Path:
    """Renders the HTML content into a PDF and saves it to a temporary file."""
    temp_dir = _get_temp_filepath("") # Get the temp directory path
    pdf_path = temp_dir / "picklist.pdf"
    
    # Use WeasyPrint to create the PDF from our HTML string
    HTML(string=html_content).write_pdf(pdf_path)
    
    return pdf_path

def get_available_printers() -> List[str]:
    """Returns a list of all available printer names on the system."""
    try:
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        return [printer[2] for printer in printers]
    except Exception as e:
        print(f"Could not enumerate printers: {e}")
        return []

def send_pdf_to_printer(pdf_path: Path, printer_name: str) -> bool:
    """Sends the specified PDF file to the specified printer."""
    try:
        # This command tells Windows to print the file using the default application
        # associated with PDFs, and specifies the target printer.
        win32api.ShellExecute(
            0,
            "printto",
            str(pdf_path),
            f'"{printer_name}"',
            ".",
            0
        )
        return True
    except Exception as e:
        print(f"Failed to print to {printer_name}: {e}")
        return False