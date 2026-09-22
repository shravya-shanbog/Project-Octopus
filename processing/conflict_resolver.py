# ==================================================
# PROJECT OCTOPUS — CONFLICT RESOLUTION ENGINE
# ==================================================

from datetime import datetime


# --------------------------------------------------
# SOURCE PRIORITY
# --------------------------------------------------

SOURCE_PRIORITY = {
    "MySQL": 3,
    "API": 3,
    "Google Sheets": 2,
    "Excel": 1,
    "CSV": 1
}


# --------------------------------------------------
# GET SOURCE PRIORITY
# --------------------------------------------------

def get_source_priority(source):
    return SOURCE_PRIORITY.get(
        source,
        0
    )


# --------------------------------------------------
# CHECK FOR CONFLICT
# --------------------------------------------------

def detect_conflict(record_a, record_b):
    differences = {}

    fields = [
        "asset_name",
        "location",
        "status",
        "last_updated"
    ]

    for field in fields:

        value_a = record_a.get(field)
        value_b = record_b.get(field)

        if value_a != value_b:

            differences[field] = {
                "record_a": value_a,
                "record_b": value_b
            }

    return {
        "has_conflict": len(differences) > 0,
        "differences": differences
    }


# --------------------------------------------------
# SELECT BEST RECORD
# --------------------------------------------------

def resolve_conflict(record_a, record_b):

    priority_a = get_source_priority(
        record_a.get("source")
    )

    priority_b = get_source_priority(
        record_b.get("source")
    )

    time_a = record_a.get("last_updated")
    time_b = record_b.get("last_updated")

    # Higher source priority wins
    if priority_a > priority_b:
        winner = record_a
        reason = "Higher source priority."

    elif priority_b > priority_a:
        winner = record_b
        reason = "Higher source priority."

    # If source priority is equal,
    # use the most recent timestamp.
    elif time_a and time_b and time_a != time_b:

        if time_a > time_b:
            winner = record_a
        else:
            winner = record_b

        reason = "More recent update."

    else:
        winner = record_a
        reason = "Equal priority; first record retained."

    return {
        "winner": winner,
        "reason": reason
    }


# --------------------------------------------------
# RESOLVE MULTIPLE RECORDS
# --------------------------------------------------

def resolve_records(records):

    if not records:
        return None

    resolved = records[0]
    conflicts = []

    for record in records[1:]:

        conflict = detect_conflict(
            resolved,
            record
        )

        if conflict["has_conflict"]:

            conflicts.append({
                "asset_id": resolved.get("asset_id"),
                "differences": conflict["differences"]
            })

            resolution = resolve_conflict(
                resolved,
                record
            )

            resolved = resolution["winner"]

    return {
        "resolved_record": resolved,
        "conflicts": conflicts,
        "conflict_count": len(conflicts)
    }