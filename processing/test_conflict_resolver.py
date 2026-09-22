# ==================================================
# PROJECT OCTOPUS — CONFLICT RESOLUTION TEST
# ==================================================

from datetime import datetime

from processing.conflict_resolver import (
    detect_conflict,
    resolve_records
)


# --------------------------------------------------
# SOURCE RECORDS
# --------------------------------------------------

mysql_record = {
    "asset_id": "A201",
    "asset_name": "Temperature Sensor",
    "location": "Gallery 2",
    "status": "Active",
    "last_updated": datetime(2026, 9, 7, 11, 20),
    "source": "MySQL"
}


excel_record = {
    "asset_id": "A201",
    "asset_name": "Temperature Sensor",
    "location": "Gallery 5",
    "status": "Active",
    "last_updated": datetime(2026, 9, 7, 11, 25),
    "source": "Excel"
}


# --------------------------------------------------
# DETECT CONFLICT
# --------------------------------------------------

conflict = detect_conflict(
    mysql_record,
    excel_record
)


print("\n=== PROJECT OCTOPUS CONFLICT TEST ===")

print(
    f"\nConflict detected: "
    f"{conflict['has_conflict']}"
)


print("\n=== DIFFERENCES ===")

for field, values in conflict["differences"].items():

    print(
        f"{field}: "
        f"{values['record_a']} "
        f"vs "
        f"{values['record_b']}"
    )


# --------------------------------------------------
# RESOLVE CONFLICT
# --------------------------------------------------

result = resolve_records(
    [
        mysql_record,
        excel_record
    ]
)


print("\n=== RESOLUTION RESULT ===")

print(
    f"Conflicts found: "
    f"{result['conflict_count']}"
)


print("\nSelected record:")

for key, value in result["resolved_record"].items():

    print(
        f"{key}: {value}"
    )