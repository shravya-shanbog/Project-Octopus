# ==================================================
# PROJECT OCTOPUS — DATA FUSION TEST
# ==================================================

import pandas as pd

from processing.data_fusion import (
    fuse_dataframes,
    remove_exact_duplicates,
    get_fusion_summary
)


# --------------------------------------------------
# SOURCE 1 — MYSQL
# --------------------------------------------------

mysql_data = pd.DataFrame([
    {
        "asset_id": "A201",
        "asset_name": "Temperature Sensor",
        "location": "Gallery 2",
        "status": "Active",
        "last_updated": "2026-09-07 11:20:00",
        "source": "MySQL",
        "confidence": 0.95
    },
    {
        "asset_id": "A202",
        "asset_name": "Control Module",
        "location": "Gallery 3",
        "status": "Maintenance",
        "last_updated": "2026-09-07 11:25:00",
        "source": "MySQL",
        "confidence": 0.96
    }
])


# --------------------------------------------------
# SOURCE 2 — EXCEL
# --------------------------------------------------

excel_data = pd.DataFrame([
    {
        "asset_id": "A203",
        "asset_name": "Power Unit",
        "location": "Zone 3",
        "status": "Active",
        "last_updated": "2026-09-07 11:30:00",
        "source": "Excel",
        "confidence": 0.88
    },
    {
        "asset_id": "A204",
        "asset_name": "Pressure Sensor",
        "location": "Lab 1",
        "status": "Inactive",
        "last_updated": "2026-09-07 11:35:00",
        "source": "Excel",
        "confidence": 0.91
    }
])


# --------------------------------------------------
# FUSE SOURCES
# --------------------------------------------------

fused_data = fuse_dataframes([
    mysql_data,
    excel_data
])


# --------------------------------------------------
# REMOVE EXACT DUPLICATES
# --------------------------------------------------

fused_data = remove_exact_duplicates(
    fused_data
)


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

summary = get_fusion_summary(
    fused_data
)


# --------------------------------------------------
# DISPLAY RESULT
# --------------------------------------------------

print("\n=== PROJECT OCTOPUS DATA FUSION TEST ===")

print("\n=== UNIFIED DATASET ===\n")

print(
    fused_data.to_string(
        index=False
    )
)

print("\n=== FUSION SUMMARY ===")

print(
    f"Total records: "
    f"{summary['total_records']}"
)

print(
    f"Unique assets: "
    f"{summary['unique_assets']}"
)

print(
    f"Sources: "
    f"{summary['sources']}"
)