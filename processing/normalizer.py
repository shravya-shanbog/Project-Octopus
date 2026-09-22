# ==================================================
# PROJECT OCTOPUS — DATA NORMALIZATION ENGINE
# ==================================================

import re
from datetime import datetime

import pandas as pd


# ==================================================
# GENERAL TEXT NORMALIZATION
# ==================================================

def normalize_text(value):
    """
    Clean general text values without changing
    their actual meaning.
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


# ==================================================
# ASSET ID NORMALIZATION
# ==================================================

def normalize_asset_id(value):
    """
    Normalize identifier formatting while preserving
    the identifier itself.
    """

    value = normalize_text(value)

    if value is None:
        return None

    value = value.upper()

    value = re.sub(
        r"\s+",
        "",
        value
    )

    value = value.replace(
        "_",
        "-"
    )

    return value


# ==================================================
# ASSET NAME NORMALIZATION
# ==================================================

def normalize_asset_name(value):
    """
    Standardize asset names and descriptions.
    """

    value = normalize_text(value)

    if value is None:
        return None

    return value


# ==================================================
# LOCATION NORMALIZATION
# ==================================================

def normalize_location(value):
    """
    Convert different representations of the same
    location into a canonical form.
    """

    value = normalize_text(value)

    if value is None:
        return None

    cleaned = value.lower()

    # Remove unnecessary punctuation.
    cleaned = re.sub(
        r"[._]+",
        " ",
        cleaned
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    ).strip()


    # ----------------------------------------------
    # Gallery
    # ----------------------------------------------

    gallery_match = re.fullmatch(
        r"gallery\s*(?:no\.?\s*)?(\d+)",
        cleaned
    )

    if gallery_match:

        number = gallery_match.group(1)

        return f"Gallery {number}"


    # ----------------------------------------------
    # Room
    # ----------------------------------------------

    room_match = re.fullmatch(
        r"room\s*(?:no\.?\s*)?(\d+)",
        cleaned
    )

    if room_match:

        number = room_match.group(1)

        return f"Room {number}"


    # ----------------------------------------------
    # Zone
    # ----------------------------------------------

    zone_match = re.fullmatch(
        r"zone\s*(?:no\.?\s*)?(\d+)",
        cleaned
    )

    if zone_match:

        number = zone_match.group(1)

        return f"Zone {number}"


    # ----------------------------------------------
    # Area
    # ----------------------------------------------

    area_match = re.fullmatch(
        r"area\s*(?:no\.?\s*)?(\d+)",
        cleaned
    )

    if area_match:

        number = area_match.group(1)

        return f"Area {number}"


    # ----------------------------------------------
    # General title formatting
    # ----------------------------------------------

    return value.title()


# ==================================================
# STATUS NORMALIZATION
# ==================================================

STATUS_MAP = {

    "active": "Active",
    "enabled": "Active",
    "online": "Active",
    "running": "Active",
    "working": "Active",
    "operational": "Active",

    "inactive": "Inactive",
    "disabled": "Inactive",
    "offline": "Inactive",
    "stopped": "Inactive",

    "maintenance": "Maintenance",
    "under maintenance": "Maintenance",
    "service": "Maintenance",

    "fault": "Fault",
    "faulty": "Fault",
    "error": "Fault",
    "failed": "Fault",
    "failure": "Fault"
}


def normalize_status(value):
    """
    Convert different status representations into
    canonical status values.
    """

    value = normalize_text(value)

    if value is None:
        return None

    cleaned = value.lower()

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    ).strip()

    return STATUS_MAP.get(
        cleaned,
        value.title()
    )


# ==================================================
# TIMESTAMP NORMALIZATION
# ==================================================

def normalize_timestamp(value):
    """
    Convert supported timestamp representations into
    a standard datetime value.
    """

    if pd.isna(value):
        return None

    if isinstance(
        value,
        datetime
    ):
        return value


    converted = pd.to_datetime(
        value,
        errors="coerce",
        format="mixed"
    )

    if pd.isna(converted):
        return None

    return converted.to_pydatetime()


# ==================================================
# COMPLETE RECORD NORMALIZATION
# ==================================================

def normalize_record(record):
    """
    Normalize a record that has already been mapped
    to the canonical schema.
    """

    normalized = {}

    normalized["asset_id"] = (
        normalize_asset_id(
            record.get("asset_id")
        )
    )

    normalized["asset_name"] = (
        normalize_asset_name(
            record.get("asset_name")
        )
    )

    normalized["location"] = (
        normalize_location(
            record.get("location")
        )
    )

    normalized["status"] = (
        normalize_status(
            record.get("status")
        )
    )

    normalized["last_updated"] = (
        normalize_timestamp(
            record.get("last_updated")
        )
    )

    return normalized


# ==================================================
# NORMALIZE DATAFRAME
# ==================================================

def normalize_dataframe(
    dataframe: pd.DataFrame,
    column_mapping: dict
) -> pd.DataFrame:
    """
    Convert a source dataframe into the canonical
    normalized representation.

    column_mapping example:

        {
            "asset_id": "DEVICE_NO",
            "asset_name": "MACHINE_DESC",
            "location": "SITE_LOC",
            "status": "CONDITION",
            "last_updated": "MODIFIED"
        }
    """

    normalized_records = []

    for _, row in dataframe.iterrows():

        record = {}

        for canonical_field, source_column in (
            column_mapping.items()
        ):

            record[canonical_field] = (
                row.get(source_column)
            )

        normalized_record = (
            normalize_record(
                record
            )
        )

        normalized_records.append(
            normalized_record
        )

    return pd.DataFrame(
        normalized_records
    )