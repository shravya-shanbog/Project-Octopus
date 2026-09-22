
# ==================================================
# PROJECT OCTOPUS — UNIVERSAL INGESTION TEST
# ==================================================

from connectors.csv_connector import CSVConnector

from processing.universal_ingestion import (
    ingest_source
)


# --------------------------------------------------
# CREATE CSV CONNECTOR
# --------------------------------------------------

connector = CSVConnector(
    {
        "file_path": "data/samples/test_inventory.csv"
    }
)


print(
    "\n=== PROJECT OCTOPUS UNIVERSAL INGESTION TEST ==="
)


# --------------------------------------------------
# ADMINISTRATOR-APPROVED MAPPING
# --------------------------------------------------

approved_mapping = {
    "asset_id": "DEVICE_NO",
    "asset_name": "MACHINE_DESC",
    "location": "SITE_LOC",
    "status": "CONDITION",
    "last_updated": "MODIFIED"
}


# --------------------------------------------------
# RUN COMPLETE INGESTION PIPELINE
# --------------------------------------------------

result = ingest_source(
    connector,
    mapping_override=approved_mapping
)


# --------------------------------------------------
# DISPLAY RESULT
# --------------------------------------------------

print("\n=== INGESTION RESULT ===")

print(
    f"Success: {result['success']}"
)


# --------------------------------------------------
# SUCCESS
# --------------------------------------------------

if result["success"]:

    print(
        f"Source ID: "
        f"{result['source_id']}"
    )

    print(
        f"Rows extracted: "
        f"{result['extraction']['row_count']}"
    )

    print(
        f"Rows validated: "
        f"{result['validation']['valid_rows']}"
    )

    print(
        f"Entities stored: "
        f"{result['stored_entities']}"
    )

    print(
        f"Data records stored: "
        f"{result['stored_data_records']}"
    )


    # --------------------------------------------------
    # APPROVED COLUMN MAPPING
    # --------------------------------------------------

    print("\n=== APPROVED COLUMN MAPPING ===")

    for (
        canonical_field,
        source_column
    ) in result["column_mapping"].items():

        print(
            f"{source_column} → "
            f"{canonical_field}"
        )


    print(
        "\n=== UNIVERSAL INGESTION TEST PASSED ==="
    )


# --------------------------------------------------
# FAILURE
# --------------------------------------------------

else:

    print(
        f"Failed at stage: "
        f"{result.get('stage')}"
    )

    print(
        f"Message: "
        f"{result.get('message')}"
    )