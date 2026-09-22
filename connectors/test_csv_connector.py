# ==================================================
# PROJECT OCTOPUS — CSV CONNECTOR TEST
# ==================================================

from connectors.csv_connector import CSVConnector


# --------------------------------------------------
# TEST FILE
# --------------------------------------------------

config = {
    "file_path": "data/samples/test_inventory.csv"
}


# --------------------------------------------------
# CREATE CONNECTOR
# --------------------------------------------------

connector = CSVConnector(config)


print("\n=== PROJECT OCTOPUS CSV CONNECTOR TEST ===")


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
# DISCOVER CSV STRUCTURE
# --------------------------------------------------

if connector.connected:

    discovery = connector.discover()

    print("\n=== DISCOVERED CSV STRUCTURE ===")

    print(
        f"File: {discovery['file_name']}"
    )

    print(
        f"Columns: {discovery['columns']}"
    )

    print(
        f"Column count: {discovery['column_count']}"
    )


# --------------------------------------------------
# EXTRACT DATA
# --------------------------------------------------

dataframe = connector.extract()

print("\n=== EXTRACTED DATA ===")

print(
    dataframe.to_string(
        index=False
    )
)


# --------------------------------------------------
# CLOSE
# --------------------------------------------------

connector.close()

print(
    "\nCSV connector test completed."
)