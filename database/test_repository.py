# ==================================================
# PROJECT OCTOPUS — DATABASE REPOSITORY TEST
# ==================================================

from datetime import datetime

from database.connection import SessionLocal
from database.repository import (
    create_asset,
    get_asset,
    get_all_assets,
    upsert_asset
)


# --------------------------------------------------
# OPEN DATABASE SESSION
# --------------------------------------------------

db = SessionLocal()


try:

    print("\n=== PROJECT OCTOPUS DATABASE TEST ===")


    # --------------------------------------------------
    # TEST RECORD
    # --------------------------------------------------

    asset_data = {
        "asset_id": "TEST-A001",
        "asset_name": "Temperature Sensor",
        "location": "Gallery 1",
        "status": "Active",
        "last_updated": datetime(2026, 9, 8, 10, 30),
        "source": "Test Import",
        "confidence": 0.95
    }


    # --------------------------------------------------
    # INSERT RECORD
    # --------------------------------------------------

    existing = get_asset(
        db,
        asset_data["asset_id"]
    )

    if existing is None:

        asset = create_asset(
            db,
            asset_data
        )

        print("\nRecord inserted successfully.")

    else:

        asset = existing

        print("\nTest record already exists.")


    # --------------------------------------------------
    # RETRIEVE RECORD
    # --------------------------------------------------

    retrieved = get_asset(
        db,
        "TEST-A001"
    )


    print("\n=== RETRIEVED RECORD ===")

    print(
        f"Asset ID: {retrieved.asset_id}"
    )

    print(
        f"Asset Name: {retrieved.asset_name}"
    )

    print(
        f"Location: {retrieved.location}"
    )

    print(
        f"Status: {retrieved.status}"
    )

    print(
        f"Last Updated: {retrieved.last_updated}"
    )

    print(
        f"Source: {retrieved.source}"
    )

    print(
        f"Confidence: {retrieved.confidence}"
    )


    # --------------------------------------------------
    # GET ALL RECORDS
    # --------------------------------------------------

    all_assets = get_all_assets(db)

    print("\n=== DATABASE SUMMARY ===")

    print(
        f"Total assets stored: "
        f"{len(all_assets)}"
    )


    # --------------------------------------------------
    # TEST UPSERT
    # --------------------------------------------------

    updated_data = {
        "asset_id": "TEST-A001",
        "asset_name": "Temperature Sensor",
        "location": "Gallery 2",
        "status": "Maintenance",
        "last_updated": datetime(2026, 9, 8, 11, 00),
        "source": "Test Import",
        "confidence": 0.98
    }


    updated_asset = upsert_asset(
        db,
        updated_data
    )


    print("\n=== UPSERT TEST ===")

    print(
        f"Updated location: "
        f"{updated_asset.location}"
    )

    print(
        f"Updated status: "
        f"{updated_asset.status}"
    )

    print(
        f"Updated confidence: "
        f"{updated_asset.confidence}"
    )


    print(
        "\nDatabase repository test completed successfully."
    )


finally:

    db.close()