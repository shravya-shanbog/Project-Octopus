# ==================================================
# PROJECT OCTOPUS — UNIVERSAL DATA EXTRACTOR
# ==================================================

from pathlib import Path
from typing import Any

import pandas as pd


# --------------------------------------------------
# SUPPORTED FILE FORMATS
# --------------------------------------------------

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls"
}


# --------------------------------------------------
# FILE TYPE DETECTION
# --------------------------------------------------

def detect_file_type(file_path: str) -> str:
    """
    Detect the file format from its extension.
    """

    extension = Path(file_path).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    return extension


# --------------------------------------------------
# CSV EXTRACTION
# --------------------------------------------------

def extract_csv(
    file_path: str
) -> pd.DataFrame:

    dataframe = pd.read_csv(
        file_path
    )

    return dataframe


# --------------------------------------------------
# EXCEL EXTRACTION
# --------------------------------------------------

def extract_excel(
    file_path: str,
    sheet_name: Any = None
) -> pd.DataFrame:

    dataframe = pd.read_excel(
        file_path,
        sheet_name=sheet_name or 0
    )

    return dataframe


# --------------------------------------------------
# FILE EXTRACTION
# --------------------------------------------------

def extract_file(
    file_path: str,
    sheet_name: Any = None
) -> pd.DataFrame:
    """
    Automatically extract CSV or Excel data.
    """

    source_type = detect_file_type(
        file_path
    )

    if source_type == ".csv":

        return extract_csv(
            file_path
        )

    if source_type in {
        ".xlsx",
        ".xls"
    }:

        return extract_excel(
            file_path,
            sheet_name
        )

    raise ValueError(
        "Unable to extract source."
    )


# --------------------------------------------------
# UNIVERSAL SOURCE EXTRACTION
# --------------------------------------------------

def extract_from_source(
    connector,
    target: Any = None
) -> pd.DataFrame:
    """
    Extract data through any Project Octopus
    connector implementing the BaseConnector
    interface.

    The connector decides how the source is
    accessed. The rest of Octopus receives the
    same DataFrame representation.
    """

    if not connector.connected:

        connector.connect()

    extracted_data = connector.extract(
        target
    )

    if not isinstance(
        extracted_data,
        pd.DataFrame
    ):

        raise TypeError(
            "Connector extraction must return "
            "a pandas DataFrame."
        )

    return extracted_data


# --------------------------------------------------
# SOURCE METADATA
# --------------------------------------------------

def build_source_metadata(
    connector
) -> dict:
    """
    Capture source/provenance information
    without modifying the original data.
    """

    return connector.get_source_info()


# --------------------------------------------------
# EXTRACTION INSPECTION
# --------------------------------------------------

def inspect_extracted_data(
    dataframe: pd.DataFrame
) -> dict:
    """
    Produce an inspection report for any
    tabular source represented as a DataFrame.
    """

    columns = [
        str(column)
        for column in dataframe.columns
    ]

    return {
        "row_count": int(
            len(dataframe)
        ),

        "column_count": int(
            len(dataframe.columns)
        ),

        "columns": columns,

        "empty_rows": int(
            dataframe.isna()
            .all(axis=1)
            .sum()
        ),

        "non_empty_rows": int(
            (
                ~dataframe.isna()
                .all(axis=1)
            ).sum()
        )
    }


# --------------------------------------------------
# NORMALIZE COLUMN LABELS FOR ANALYSIS ONLY
# --------------------------------------------------

def get_source_columns(
    dataframe: pd.DataFrame
) -> list[str]:

    return [
        str(column).strip()
        for column in dataframe.columns
    ]


# --------------------------------------------------
# PRESERVE ORIGINAL RECORD
# --------------------------------------------------

def preserve_original_records(
    dataframe: pd.DataFrame
) -> list[dict]:
    """
    Convert source rows into dictionaries while
    keeping the original source fields untouched.

    This is important because Project Octopus
    must support appliances having completely
    different fields.
    """

    records = dataframe.to_dict(
        orient="records"
    )

    return records