# ==================================================
# PROJECT OCTOPUS — NORMALIZATION TEST
# ==================================================

import pandas as pd

from processing.normalizer import normalize_dataframe


# --------------------------------------------------
# TEST DATA
# --------------------------------------------------

data = {
    "DEVICE_NO": [
        "a201",
        "A-202",
        " a203 ",
        "A_204"
    ],

    "MACHINE_DESC": [
        "Temperature Sensor",
        "Control Module",
        "Power Unit",
        "Pressure Sensor"
    ],

    "SITE_LOC": [
        "Gallery-1",
        "GALLERY 2",
        "Gallery No. 3",
        "Room-4"
    ],

    "CONDITION": [
        "active",
        "ONLINE",
        "maintenance",
        "offline"
    ],

    "MODIFIED": [
        "2026-09-07 11:20",
        "2026/09/07 11:25",
        "07-09-2026 11:30",
        "September 7, 2026 11:35"
    ]
}


dataframe = pd.DataFrame(data)


# --------------------------------------------------
# SOURCE → CANONICAL MAPPING
# --------------------------------------------------

column_mapping = {
    "asset_id": "DEVICE_NO",
    "asset_name": "MACHINE_DESC",
    "location": "SITE_LOC",
    "status": "CONDITION",
    "last_updated": "MODIFIED"
}


# --------------------------------------------------
# NORMALIZE
# --------------------------------------------------

normalized = normalize_dataframe(
    dataframe,
    column_mapping
)


# --------------------------------------------------
# DISPLAY RESULT
# --------------------------------------------------

print("\n=== PROJECT OCTOPUS NORMALIZATION TEST ===")

print("\nNORMALIZED DATA:\n")

print(
    normalized.to_string(
        index=False
    )
)


print("\n=== DATA TYPES ===")

print(
    normalized.dtypes
)