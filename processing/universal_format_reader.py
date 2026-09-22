from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests


# ============================================================
# PROJECT OCTOPUS
# UNIVERSAL FORMAT READER
#
# Converts different structured sources into one common
# structured representation for the Octopus processing engine.
#
# Supported:
# CSV
# XLS
# XLSX
# JSON
# JSONL / NDJSON
# XML
# YAML / YML
# Google Sheets URL
# REST/API JSON URL
# ============================================================


SUPPORTED_FILE_EXTENSIONS = {
    ".csv",
    ".xls",
    ".xlsx",
    ".json",
    ".jsonl",
    ".ndjson",
    ".xml",
    ".yaml",
    ".yml",
}


def _json_to_dataframe(data: Any) -> pd.DataFrame:
    """Convert common JSON structures into a DataFrame."""

    if isinstance(data, list):
        return pd.json_normalize(data)

    if isinstance(data, dict):

        for key in ("data", "results", "items", "records"):

            value = data.get(key)

            if isinstance(value, list):
                return pd.json_normalize(value)

        return pd.json_normalize([data])

    raise ValueError("Unsupported JSON structure.")


def _read_yaml(path: Path) -> pd.DataFrame:
    """Read a YAML/YML file."""

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for YAML support."
        ) from exc

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = yaml.safe_load(file)

    return _json_to_dataframe(data)


def _read_google_sheet_url(url: str) -> pd.DataFrame:
    """
    Read a Google Sheet using its CSV export endpoint.

    Public/published sheets can be read this way.
    Private sheets will later use authenticated Google API access.
    """

    if "docs.google.com/spreadsheets" not in url:
        raise ValueError("Invalid Google Sheets URL.")

    if "/export" in url:

        csv_url = url

    else:

        parts = url.split("/")

        try:

            spreadsheet_index = parts.index("d")

            spreadsheet_id = (
                parts[spreadsheet_index + 1]
            )

        except (
            ValueError,
            IndexError,
        ) as exc:

            raise ValueError(
                "Could not determine Google Spreadsheet ID."
            ) from exc

        gid = "0"

        if "gid=" in url:

            gid = (
                url
                .split("gid=", 1)[1]
                .split("&", 1)[0]
            )

        csv_url = (
            "https://docs.google.com/"
            "spreadsheets/d/"
            f"{spreadsheet_id}"
            "/export?format=csv"
            f"&gid={gid}"
        )

    response = requests.get(
        csv_url,
        timeout=30,
    )

    response.raise_for_status()

    return pd.read_csv(
        io.StringIO(response.text)
    )


def read_source(
    source: str | Path,
    source_type: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Universal Octopus source reader.

    Returns:
        DataFrame
        Source metadata
    """

    source_value = str(source)

    # ========================================================
    # GOOGLE SHEETS
    # ========================================================

    if (
        source_value.startswith(
            "https://docs.google.com/spreadsheets/"
        )
        or source_value.startswith(
            "http://docs.google.com/spreadsheets/"
        )
    ):

        frame = _read_google_sheet_url(
            source_value
        )

        return frame, {
            "source_type": "google_sheets",
            "format": "google_sheets",
            "source": source_value,
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    # ========================================================
    # HTTP / REST API JSON
    # ========================================================

    if (
        source_value.startswith("http://")
        or source_value.startswith("https://")
    ):

        response = requests.get(
            source_value,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        frame = _json_to_dataframe(
            data
        )

        return frame, {
            "source_type": (
                source_type or "api"
            ),
            "format": "json_api",
            "source": source_value,
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    # ========================================================
    # LOCAL FILE
    # ========================================================

    path = (
        Path(source)
        .expanduser()
        .resolve()
    )

    if not path.exists():

        raise FileNotFoundError(
            f"Source not found: {path}"
        )

    extension = path.suffix.lower()

    # ========================================================
    # CSV
    # ========================================================

    if extension == ".csv":

        frame = pd.read_csv(path)

        return frame, {
            "source_type": (
                source_type or "file"
            ),
            "format": "csv",
            "source": str(path),
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    # ========================================================
    # EXCEL
    # ========================================================

    if extension in {
        ".xls",
        ".xlsx",
    }:

        frame = pd.read_excel(path)

        return frame, {
            "source_type": (
                source_type or "file"
            ),
            "format": extension.lstrip("."),
            "source": str(path),
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    # ========================================================
    # JSON
    # ========================================================

    if extension == ".json":

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        frame = _json_to_dataframe(
            data
        )

        return frame, {
            "source_type": (
                source_type or "file"
            ),
            "format": "json",
            "source": str(path),
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    # ========================================================
    # JSONL / NDJSON
    # ========================================================

    if extension in {
        ".jsonl",
        ".ndjson",
    }:

        frame = pd.read_json(
            path,
            lines=True,
        )

        return frame, {
            "source_type": (
                source_type or "file"
            ),
            "format": "jsonl",
            "source": str(path),
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    # ========================================================
    # XML
    # ========================================================

    if extension == ".xml":

        frame = pd.read_xml(
            path
        )

        return frame, {
            "source_type": (
                source_type or "file"
            ),
            "format": "xml",
            "source": str(path),
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    # ========================================================
    # YAML / YML
    # ========================================================

    if extension in {
        ".yaml",
        ".yml",
    }:

        frame = _read_yaml(
            path
        )

        return frame, {
            "source_type": (
                source_type or "file"
            ),
            "format": "yaml",
            "source": str(path),
            "rows": len(frame),
            "columns": list(frame.columns),
        }

    raise ValueError(
        f"Unsupported source format: {extension}"
    )


def read_text_or_object(
    data: str,
    source_type: str = "json",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Read JSON/YAML data directly from memory.
    Useful for API responses and future connectors.
    """

    normalized_type = source_type.lower()

    if normalized_type == "json":

        parsed = json.loads(
            data
        )

    elif normalized_type in {
        "yaml",
        "yml",
    }:

        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(
                "PyYAML is required for YAML support."
            ) from exc

        parsed = yaml.safe_load(
            data
        )

    else:

        raise ValueError(
            f"Unsupported in-memory format: {source_type}"
        )

    frame = _json_to_dataframe(
        parsed
    )

    return frame, {
        "source_type": source_type,
        "format": source_type,
        "source": "memory",
        "rows": len(frame),
        "columns": list(frame.columns),
    }