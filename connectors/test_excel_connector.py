# ==================================================
# PROJECT OCTOPUS — EXCEL CONNECTOR TEST
# ==================================================

from connectors.excel_connector import ExcelConnector


# --------------------------------------------------
# TEST FILE
# --------------------------------------------------

config = {
    "file_path": "data/samples/test_inventory.xlsx"
}


# --------------------------------------------------
# CREATE CONNECTOR
# --------------------------------------------------

connector = ExcelConnector(config)


print("\n=== PROJECT OCTOPUS EXCEL CONNECTOR TEST ===")


# --------------------------------------------------
# CONNECTION TEST
# --------------------------------------------------

print(
    f"\nConnection available: "
    f"{connector.test_connection()}"
)


# --------------------------------------------------
# SOURCE INFORMATION
# --------------------------------------------------

print("\n=== SOURCE INFORMATION ===")

print(
    connector.get_source_info()
)


# --------------------------------------------------
# DISCOVER SHEETS
# --------------------------------------------------

if connector.connected:

    sheets = connector.discover()

    print("\n=== DISCOVERED SHEETS ===")

    print(sheets)


# --------------------------------------------------
# CLOSE
# --------------------------------------------------

connector.close()

print("\nExcel connector test completed.")