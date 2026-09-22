# ==================================================
# PROJECT OCTOPUS — DATA FUSION ENGINE
# ==================================================

import pandas as pd


# --------------------------------------------------
# CANONICAL FIELDS
# --------------------------------------------------

CANONICAL_FIELDS = [
    "asset_id",
    "asset_name",
    "location",
    "status",
    "last_updated",
    "source",
    "confidence"
]


# --------------------------------------------------
# PREPARE RECORD
# --------------------------------------------------

def prepare_record(record, source=None, confidence=1.0):

    prepared = {}

    for field in CANONICAL_FIELDS:
        prepared[field] = record.get(field)

    if source is not None:
        prepared["source"] = source

    if prepared["confidence"] is None:
        prepared["confidence"] = confidence

    return prepared


# --------------------------------------------------
# FUSE RECORDS
# --------------------------------------------------

def fuse_records(records):

    if not records:
        return pd.DataFrame(
            columns=CANONICAL_FIELDS
        )

    prepared_records = []

    for record in records:

        prepared = prepare_record(
            record
        )

        prepared_records.append(
            prepared
        )

    dataframe = pd.DataFrame(
        prepared_records,
        columns=CANONICAL_FIELDS
    )

    return dataframe


# --------------------------------------------------
# FUSE MULTIPLE SOURCE DATASETS
# --------------------------------------------------

def fuse_dataframes(dataframes):

    if not dataframes:
        return pd.DataFrame(
            columns=CANONICAL_FIELDS
        )

    prepared_dataframes = []

    for dataframe in dataframes:

        current = dataframe.copy()

        for field in CANONICAL_FIELDS:

            if field not in current.columns:
                current[field] = None

        current = current[
            CANONICAL_FIELDS
        ]

        prepared_dataframes.append(
            current
        )

    fused = pd.concat(
        prepared_dataframes,
        ignore_index=True
    )

    return fused


# --------------------------------------------------
# REMOVE EXACT DUPLICATES
# --------------------------------------------------

def remove_exact_duplicates(dataframe):

    if dataframe.empty:
        return dataframe

    return dataframe.drop_duplicates(
        subset=[
            "asset_id",
            "asset_name",
            "location",
            "status",
            "last_updated",
            "source"
        ]
    ).reset_index(drop=True)


# --------------------------------------------------
# FUSION SUMMARY
# --------------------------------------------------

def get_fusion_summary(dataframe):

    return {
        "total_records": len(dataframe),
        "unique_assets": (
            dataframe["asset_id"]
            .nunique()
            if "asset_id" in dataframe.columns
            else 0
        ),
        "sources": (
            dataframe["source"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
            if "source" in dataframe.columns
            else []
        )
    }