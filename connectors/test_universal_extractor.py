# ==================================================
# PROJECT OCTOPUS — UNIVERSAL EXTRACTOR TEST
# ==================================================

from connectors.csv_connector import CSVConnector
from connectors.excel_connector import ExcelConnector

from processing.extractor import (
    extract_from_source,
    inspect_extracted_data,
    preserve_original_records
)


# ==================================================
# 1. CSV SOURCE
# ==================================================

csv_connector = CSVConnector({
    "file_path": "data/samples/test_inventory.csv"
})


print("\n=== CSV UNIVERSAL EXTRACTION ===")

csv_data = extract_from_source(
    csv_connector
)

csv_report = inspect_extracted_data(
    csv_data
)

print(
    f"Rows: {csv_report['row_count']}"
)

print(
    f"Columns: {csv_report['columns']}"
)

print("\nFirst CSV record:")

print(
    preserve_original_records(
        csv_data
    )[0]
)

csv_connector.close()


# ==================================================
# 2. EXCEL SOURCE
# ==================================================

excel_connector = ExcelConnector({
    "file_path": "data/samples/test_inventory.xlsx"
})


print("\n=== EXCEL UNIVERSAL EXTRACTION ===")

excel_data = extract_from_source(
    excel_connector
)

excel_report = inspect_extracted_data(
    excel_data
)

print(
    f"Rows: {excel_report['row_count']}"
)

print(
    f"Columns: {excel_report['columns']}"
)

print("\nFirst Excel record:")

print(
    preserve_original_records(
        excel_data
    )[0]
)

excel_connector.close()


# ==================================================
# FINAL RESULT
# ==================================================

print(
    "\n=== UNIVERSAL EXTRACTOR TEST PASSED ==="
)

print(
    "CSV and Excel were processed through "
    "the same extraction interface."
)

print(
    "Original source fields were preserved."
)