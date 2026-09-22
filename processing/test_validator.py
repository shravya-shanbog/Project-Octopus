# ==================================================
# PROJECT OCTOPUS — VALIDATION TEST
# ==================================================

import pandas as pd

from processing.validator import validate_dataframe


# --------------------------------------------------
# TEST DATA
# --------------------------------------------------

data = {
    "asset_id": [
        "A201",
        "A202",
        "A202",
        None
    ],

    "asset_name": [
        "Temperature Sensor",
        "Control Module",
        "Power Unit",
        "Pressure Sensor"
    ],

    "location": [
        "Room 4",
        "Gallery 2",
        "Zone 3",
        "Lab 1"
    ],

    "status": [
        "Active",
        "Maintenance",
        "UnknownStatus",
        "Inactive"
    ],

    "last_updated": [
        "2026-09-07 11:20",
        "2026-09-07 11:25",
        "2026-09-07 11:30",
        "not-a-date"
    ]
}


dataframe = pd.DataFrame(data)


# --------------------------------------------------
# VALIDATE
# --------------------------------------------------

validation_report = validate_dataframe(
    dataframe
)


# --------------------------------------------------
# DISPLAY SUMMARY
# --------------------------------------------------

print("\n=== PROJECT OCTOPUS VALIDATION TEST ===")

print(
    f"\nTotal rows: "
    f"{validation_report['total_rows']}"
)

print(
    f"Valid rows: "
    f"{validation_report['valid_rows']}"
)

print(
    f"Invalid rows: "
    f"{validation_report['invalid_rows']}"
)

print(
    f"Duplicate asset IDs: "
    f"{validation_report['duplicate_asset_ids']}"
)


# --------------------------------------------------
# DISPLAY ROW RESULTS
# --------------------------------------------------

print("\n=== ROW VALIDATION RESULTS ===")

for result in validation_report["row_results"]:

    print(
        f"\nRow {result['row_number']}"
    )

    print(
        f"Valid: "
        f"{result['valid']}"
    )

    if result["errors"]:

        for error in result["errors"]:
            print(
                f"  ERROR: {error}"
            )

    else:
        print("  No errors.")