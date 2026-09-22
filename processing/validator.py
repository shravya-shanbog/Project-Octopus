# ==================================================
# PROJECT OCTOPUS — DATA VALIDATION ENGINE
# ==================================================

import pandas as pd


# --------------------------------------------------
# VALID VALUES
# --------------------------------------------------

VALID_STATUSES = {
    "Active",
    "Inactive",
    "Maintenance",
    "Fault"
}


# --------------------------------------------------
# VALIDATE REQUIRED FIELDS
# --------------------------------------------------

def validate_required_fields(record):
    errors = []

    required_fields = [
        "asset_id",
        "asset_name",
        "location",
        "last_updated"
    ]

    for field in required_fields:
        value = record.get(field)

        if value is None or pd.isna(value) or str(value).strip() == "":
            errors.append(
                f"Missing required field: {field}"
            )

    return errors


# --------------------------------------------------
# VALIDATE STATUS
# --------------------------------------------------

def validate_status(status):
    if status is None or pd.isna(status):
        return ["Missing status."]

    if str(status).strip() not in VALID_STATUSES:
        return [
            f"Invalid status: {status}"
        ]

    return []


# --------------------------------------------------
# VALIDATE TIMESTAMP
# --------------------------------------------------

def validate_timestamp(timestamp):
    if timestamp is None or pd.isna(timestamp):
        return ["Missing last_updated timestamp."]

    converted = pd.to_datetime(
        timestamp,
        errors="coerce"
    )

    if pd.isna(converted):
        return [
            f"Invalid timestamp: {timestamp}"
        ]

    return []


# --------------------------------------------------
# VALIDATE SINGLE RECORD
# --------------------------------------------------

def validate_record(record):
    errors = []

    errors.extend(
        validate_required_fields(record)
    )

    errors.extend(
        validate_status(
            record.get("status")
        )
    )

    errors.extend(
        validate_timestamp(
            record.get("last_updated")
        )
    )

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


# --------------------------------------------------
# VALIDATE DATAFRAME
# --------------------------------------------------

def validate_dataframe(dataframe):
    results = []

    for index, row in dataframe.iterrows():

        record = row.to_dict()

        validation = validate_record(record)

        results.append({
            "row_number": index + 1,
            "valid": validation["valid"],
            "errors": validation["errors"]
        })

    # --------------------------------------------------
    # DUPLICATE ASSET ID CHECK
    # --------------------------------------------------

    duplicate_ids = []

    if "asset_id" in dataframe.columns:

        duplicated = dataframe[
            dataframe["asset_id"].duplicated(
                keep=False
            )
        ]

        duplicate_ids = (
            duplicated["asset_id"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    return {
        "row_results": results,
        "duplicate_asset_ids": duplicate_ids,
        "total_rows": len(dataframe),
        "valid_rows": sum(
            result["valid"]
            for result in results
        ),
        "invalid_rows": sum(
            not result["valid"]
            for result in results
        )
    }