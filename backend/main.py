from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from processing.universal_format_reader import read_source


# ============================================================
# PROJECT OCTOPUS — UNIFIED HETEROGENEOUS DATA BACKEND
# ============================================================
# Local structured sources:
#   CSV / XLS / XLSX / JSON / JSONL / NDJSON / XML / YAML / YML
# Remote structured sources:
#   Google Sheets URLs / REST API JSON URLs
#
# Common pipeline:
#   Connect -> Extract -> Schema Detection -> Adaptive Mapping
#   -> Normalize -> Validate -> Identity -> Conflict Handling
#   -> PostgreSQL -> Events -> Search / Dashboard
# ============================================================


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
IMPORT_DIR = DATA_DIR / "imports"
INVENTORY_FILE = DATA_DIR / "computer_inventory.json"
APPROVED_MAPPING_FILE = BASE_DIR / "agent" / "approved_mapping.json"
SYNC_STATE_FILE = DATA_DIR / "sync_state.json"

load_dotenv(BASE_DIR / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = (
    create_engine(DATABASE_URL, pool_pre_ping=True)
    if DATABASE_URL
    else None
)

app = FastAPI(
    title="Project Octopus",
    version="5.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )


SUPPORTED_LOCAL_EXTENSIONS = {
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


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not SYNC_STATE_FILE.exists():
        SYNC_STATE_FILE.write_text("{}", encoding="utf-8")

    if engine is not None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS octopus_system_state (
                            state_key TEXT PRIMARY KEY,
                            state_value JSONB,
                            updated_at TIMESTAMPTZ DEFAULT NOW()
                        )
                        """
                    )
                )
        except Exception as exc:
            print(
                f"[OCTOPUS] Database startup warning: {exc}",
                flush=True,
            )


# ============================================================
# GENERAL HELPERS
# ============================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(key): json_safe(val)
            for key, val in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value


def jsonable_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            str(key): json_safe(value)
            for key, value in row.items()
        }
        for row in rows
    ]


def query_rows(
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if engine is None:
        return []

    with engine.connect() as conn:
        result = conn.execute(
            text(sql),
            params or {},
        )
        return [dict(row._mapping) for row in result]


def table_columns(table_name: str) -> set[str]:
    if engine is None:
        return set()

    try:
        rows = query_rows(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
            """,
            {"table_name": table_name},
        )
        return {
            str(row["column_name"])
            for row in rows
        }
    except Exception:
        return set()


def column_map_for_table(
    table_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    columns = table_columns(table_name)
    if not columns:
        return {}

    return {
        key: value
        for key, value in payload.items()
        if key in columns
    }


def execute_insert(
    table_name: str,
    payload: dict[str, Any],
) -> bool:
    if engine is None:
        return False

    clean = column_map_for_table(
        table_name,
        payload,
    )

    if not clean:
        return False

    columns = list(clean.keys())
    values = {
        f"value_{column}": clean[column]
        for column in columns
    }

    column_sql = ", ".join(
        f'"{column}"'
        for column in columns
    )

    value_sql = ", ".join(
        f":value_{column}"
        for column in columns
    )

    sql = text(
        f'INSERT INTO "{table_name}" '
        f'({column_sql}) VALUES ({value_sql})'
    )

    with engine.begin() as conn:
        conn.execute(sql, values)

    return True


def execute_update_by_id(
    table_name: str,
    id_column: str,
    id_value: Any,
    payload: dict[str, Any],
) -> bool:
    if engine is None:
        return False

    clean = column_map_for_table(
        table_name,
        payload,
    )
    clean.pop(id_column, None)

    if not clean:
        return False

    if id_column not in table_columns(table_name):
        return False

    assignments = ", ".join(
        f'"{column}" = :value_{column}'
        for column in clean
    )

    values = {
        f"value_{column}": clean[column]
        for column in clean
    }
    values["id_value"] = id_value

    sql = text(
        f'UPDATE "{table_name}" '
        f'SET {assignments} '
        f'WHERE "{id_column}" = :id_value'
    )

    with engine.begin() as conn:
        conn.execute(sql, values)

    return True


def stable_hash(
    value: str,
    length: int = 32,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()[:length]


def read_inventory() -> dict[str, Any]:
    if not INVENTORY_FILE.exists():
        return {
            "success": False,
            "computer_name": "unknown",
            "generated_at": None,
            "drives": [],
            "total_files": 0,
            "files": [],
        }

    try:
        data = json.loads(
            INVENTORY_FILE.read_text(
                encoding="utf-8"
            )
        )
        data["success"] = True
        return data
    except Exception as exc:
        return {
            "success": False,
            "computer_name": "unknown",
            "generated_at": None,
            "drives": [],
            "total_files": 0,
            "files": [],
            "error": str(exc),
        }


def computer_source_id(
    data: dict[str, Any],
) -> str:
    return (
        "computer:"
        + str(
            data.get(
                "computer_name",
                "unknown",
            )
        )
    )


def computer_entity_id(
    path_value: str,
) -> str:
    return (
        "computer_file:"
        + stable_hash(path_value, 32)
    )


# ============================================================
# AUTHENTICATION
# ============================================================

class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/login")
def login(request: LoginRequest):
    if (
        request.email == "admin@projectoctopus.com"
        and request.password == "Octopus@123"
    ):
        return {
            "success": True,
            "user": {
                "email": request.email,
                "role": "admin",
            },
        }

    raise HTTPException(
        status_code=401,
        detail="Invalid email or password.",
    )


# ============================================================
# ROOT / HEALTH / DATABASE
# ============================================================

@app.get("/")
def home():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)

    return {
        "project": "Project Octopus",
        "status": "online",
    }


@app.get("/health")
def health():
    return {
        "success": True,
        "project": "Project Octopus",
        "backend": "online",
    }


@app.get("/api/database/test")
def database_test():
    if engine is None:
        return {
            "success": False,
            "database": "PostgreSQL",
            "connected": False,
            "message": "DATABASE_URL is not configured.",
        }

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        return {
            "success": True,
            "database": "PostgreSQL",
            "connected": True,
        }
    except Exception as exc:
        return {
            "success": False,
            "database": "PostgreSQL",
            "connected": False,
            "message": str(exc),
        }


# ============================================================
# CANONICAL SCHEMA / ADAPTIVE MAPPING
# ============================================================

CANONICAL_FIELDS = [
    "asset_id",
    "asset_name",
    "location",
    "status",
    "last_updated",
]

ALIASES: dict[str, list[str]] = {
    "asset_id": [
        "asset_id",
        "asset no",
        "asset_no",
        "asset number",
        "device_no",
        "device no",
        "device id",
        "device_number",
        "equipment_id",
        "equipment id",
        "machine_id",
        "machine id",
        "id",
        "uid",
        "serial",
        "serial_no",
        "serial number",
    ],
    "asset_name": [
        "asset_name",
        "asset name",
        "name",
        "machine_desc",
        "machine desc",
        "machine_name",
        "machine name",
        "description",
        "equipment",
        "equipment name",
        "device",
        "device name",
        "item",
    ],
    "location": [
        "location",
        "place",
        "site_loc",
        "site loc",
        "site",
        "current location",
        "current_location",
        "room",
        "zone",
        "area",
        "gallery",
    ],
    "status": [
        "status",
        "condition",
        "state",
        "operational status",
        "device status",
    ],
    "last_updated": [
        "last_updated",
        "last updated",
        "modified",
        "modified_at",
        "modified at",
        "updated",
        "updated_at",
        "updated at",
        "timestamp",
        "time",
        "date modified",
    ],
}


def normalize_column_name(value: Any) -> str:
    result = str(value).strip().lower()

    for character in [
        "-",
        "/",
        ".",
        "(",
        ")",
        "[",
        "]",
    ]:
        result = result.replace(character, " ")

    return " ".join(result.split())


def mapping_confidence(
    source_column: str,
    canonical: str,
    frame: pd.DataFrame,
) -> float:
    column = normalize_column_name(
        source_column
    )

    aliases = {
        normalize_column_name(alias)
        for alias in ALIASES[canonical]
    }

    exact_score = (
        1.0
        if column in aliases
        else 0.0
    )

    canonical_tokens = set(
        normalize_column_name(
            canonical
        ).split()
    )
    source_tokens = set(column.split())

    token_score = 0.0

    if canonical_tokens and source_tokens:
        token_score = (
            len(canonical_tokens & source_tokens)
            / len(canonical_tokens | source_tokens)
        )

    value_score = 0.0

    try:
        sample = (
            frame[source_column]
            .dropna()
            .head(20)
        )

        values = [
            str(value).strip().lower()
            for value in sample.tolist()
        ]

        if canonical == "status":
            known = {
                "active",
                "inactive",
                "online",
                "offline",
                "working",
                "maintenance",
                "fault",
                "running",
                "stopped",
            }

            if values:
                value_score = (
                    sum(value in known for value in values)
                    / len(values)
                )

        elif canonical == "last_updated":
            if values:
                parsed = pd.to_datetime(
                    sample,
                    errors="coerce",
                    format="mixed",
                )
                value_score = float(
                    parsed.notna().mean()
                )

        elif canonical == "location":
            if values:
                words = (
                    "gallery",
                    "room",
                    "zone",
                    "area",
                    "building",
                    "floor",
                    "rack",
                    "site",
                    "lab",
                )
                value_score = (
                    sum(
                        any(
                            word in value
                            for word in words
                        )
                        for value in values
                    )
                    / len(values)
                )

        elif canonical == "asset_id":
            if values:
                value_score = (
                    sum(
                        len(value) <= 40
                        and any(
                            char.isdigit()
                            for char in value
                        )
                        for value in values
                    )
                    / len(values)
                )

        elif canonical == "asset_name":
            if values:
                value_score = (
                    sum(len(value) > 1 for value in values)
                    / len(values)
                )

    except Exception:
        value_score = 0.0

    score = (
        0.40 * exact_score
        + 0.40 * value_score
        + 0.20 * token_score
    )

    return round(
        min(max(score, 0.0), 1.0),
        2,
    )


def detect_mapping(
    frame: pd.DataFrame,
) -> dict[str, Any]:
    candidates = []
    selected: dict[str, str] = {}
    used_columns: set[str] = set()

    for column in frame.columns:
        scores = []

        for canonical in CANONICAL_FIELDS:
            score = mapping_confidence(
                str(column),
                canonical,
                frame,
            )
            scores.append((score, canonical))

        scores.sort(reverse=True)
        best_score, best_canonical = scores[0]

        if (
            best_score >= 0.80
            and str(column) not in used_columns
        ):
            if best_canonical not in selected:
                selected[best_canonical] = str(column)
                used_columns.add(str(column))
                decision = "AUTO_MAP"
            else:
                decision = "REVIEW"
        elif best_score >= 0.60:
            decision = "REVIEW"
        else:
            decision = "UNMAPPED"

        candidates.append(
            {
                "source_column": str(column),
                "canonical_field": best_canonical,
                "confidence": best_score,
                "confidence_percent": int(best_score * 100),
                "decision": decision,
                "alternatives": [
                    {
                        "canonical_field": candidate,
                        "confidence": score,
                    }
                    for score, candidate in scores[:3]
                ],
            }
        )

    return {
        "mapping": selected,
        "candidates": candidates,
        "required_fields": CANONICAL_FIELDS,
        "complete": all(
            field in selected
            for field in CANONICAL_FIELDS
        ),
    }


# ============================================================
# NORMALIZATION
# ============================================================

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
    "failure": "Fault",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    result = " ".join(
        str(value).strip().split()
    )

    return result or None


def normalize_asset_id(
    value: Any,
) -> str | None:
    value = clean_text(value)
    if value is None:
        return None

    return (
        value.upper()
        .replace(" ", "")
        .replace("_", "-")
    )


def normalize_location(
    value: Any,
) -> str | None:
    value = clean_text(value)
    if value is None:
        return None

    raw = (
        value.lower()
        .replace("_", " ")
        .replace(".", " ")
    )
    raw = " ".join(raw.split())

    import re

    for prefix, title in [
        ("gallery", "Gallery"),
        ("room", "Room"),
        ("zone", "Zone"),
        ("area", "Area"),
    ]:
        match = re.fullmatch(
            rf"{prefix}\s*(?:no\.?\s*)?(\d+)",
            raw,
        )
        if match:
            return f"{title} {match.group(1)}"

    return value.title()


def normalize_status(
    value: Any,
) -> str | None:
    value = clean_text(value)
    if value is None:
        return None

    return STATUS_MAP.get(
        value.lower(),
        value.title(),
    )


def normalize_timestamp(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    try:
        parsed = pd.to_datetime(
            value,
            errors="coerce",
            format="mixed",
        )

        if pd.isna(parsed):
            return None

        return parsed.to_pydatetime()
    except Exception:
        return None


def normalize_dataframe(
    frame: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    records = []

    for _, row in frame.iterrows():
        records.append(
            {
                "asset_id": (
                    normalize_asset_id(
                        row.get(mapping["asset_id"])
                    )
                    if mapping.get("asset_id")
                    else None
                ),
                "asset_name": (
                    clean_text(
                        row.get(mapping["asset_name"])
                    )
                    if mapping.get("asset_name")
                    else None
                ),
                "location": (
                    normalize_location(
                        row.get(mapping["location"])
                    )
                    if mapping.get("location")
                    else None
                ),
                "status": (
                    normalize_status(
                        row.get(mapping["status"])
                    )
                    if mapping.get("status")
                    else None
                ),
                "last_updated": (
                    normalize_timestamp(
                        row.get(mapping["last_updated"])
                    )
                    if mapping.get("last_updated")
                    else None
                ),
            }
        )

    return pd.DataFrame(
        records,
        columns=CANONICAL_FIELDS,
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_record(
    record: dict[str, Any],
) -> list[str]:
    errors = []

    for field in [
        "asset_id",
        "asset_name",
        "location",
        "last_updated",
    ]:
        value = record.get(field)
        if value is None or str(value).strip() == "":
            errors.append(
                f"Missing required field: {field}"
            )

    status = record.get("status")

    if status is None:
        errors.append("Missing status.")
    elif status not in {
        "Active",
        "Inactive",
        "Maintenance",
        "Fault",
    }:
        errors.append(
            f"Invalid status: {status}"
        )

    return errors


def validate_dataframe(
    frame: pd.DataFrame,
) -> dict[str, Any]:
    row_results = []

    for index, row in frame.iterrows():
        errors = validate_record(
            row.to_dict()
        )
        row_results.append(
            {
                "row_number": index + 1,
                "valid": not errors,
                "errors": errors,
            }
        )

    duplicate_asset_ids: list[str] = []

    if "asset_id" in frame.columns:
        duplicate_asset_ids = (
            frame[
                frame["asset_id"].duplicated(
                    keep=False
                )
            ]["asset_id"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    return {
        "row_results": row_results,
        "duplicate_asset_ids": duplicate_asset_ids,
        "total_rows": len(frame),
        "valid_rows": sum(
            item["valid"]
            for item in row_results
        ),
        "invalid_rows": sum(
            not item["valid"]
            for item in row_results
        ),
    }


# ============================================================
# EXTRACTION
# ============================================================

def extract_dataframe(
    path: Path,
    connector_type: str | None = None,
) -> pd.DataFrame:
    suffix = path.suffix.lower()
    connector = (connector_type or "").lower()

    # Keep the existing Octopus CSV connector where possible.
    if suffix == ".csv" or connector == "csv":
        try:
            from connectors.csv_connector import CSVConnector

            csv_connector = CSVConnector(
                {"file_path": str(path)}
            )
            csv_connector.connect()
            return csv_connector.extract()
        except Exception:
            return pd.read_csv(path)

    # Keep the existing Octopus Excel connector where possible.
    if (
        suffix in {".xls", ".xlsx"}
        or connector == "excel"
    ):
        try:
            from connectors.excel_connector import ExcelConnector

            excel_connector = ExcelConnector(
                {"file_path": str(path)}
            )
            excel_connector.connect()
            return excel_connector.extract()
        except Exception:
            return pd.read_excel(path)

    # Pass other structured local formats through the new reader.
    if suffix in {
        ".json",
        ".jsonl",
        ".ndjson",
        ".xml",
        ".yaml",
        ".yml",
    }:
        frame, _metadata = read_source(
            path,
            source_type=connector or "file",
        )
        return frame

    raise ValueError(
        f"Unsupported source format: {suffix}"
    )


# ============================================================
# SOURCE / ENTITY PERSISTENCE
# ============================================================

def upsert_source(
    source_id: str,
    source_name: str,
    source_type: str,
    metadata: dict[str, Any],
) -> None:
    if engine is None or not table_columns("sources"):
        return

    payload = {
        "source_id": source_id,
        "source_name": source_name,
        "source_type": source_type,
        "status": "ONLINE",
        "last_sync_at": utc_now(),
        "metadata": json.dumps(
            json_safe(metadata)
        ),
    }

    existing = query_rows(
        """
        SELECT source_id
        FROM sources
        WHERE source_id = :source_id
        LIMIT 1
        """,
        {"source_id": source_id},
    )

    if existing:
        execute_update_by_id(
            "sources",
            "source_id",
            source_id,
            payload,
        )
    else:
        payload["created_at"] = utc_now()
        execute_insert(
            "sources",
            payload,
        )


def existing_entity(
    entity_id: str,
) -> dict[str, Any] | None:
    if engine is None or not table_columns("entities"):
        return None

    try:
        rows = query_rows(
            """
            SELECT *
            FROM entities
            WHERE entity_id = :entity_id
            LIMIT 1
            """,
            {"entity_id": entity_id},
        )
        return rows[0] if rows else None
    except Exception:
        return None


def persist_entity(
    entity_id: str,
    canonical: dict[str, Any],
    source_id: str,
    source_name: str,
    source_type: str,
    original_payload: dict[str, Any],
    mapping: dict[str, str],
    confidence: float,
) -> str:
    if engine is None or not table_columns("entities"):
        return "NO_DATABASE"

    attributes = {
        "canonical": json_safe(canonical),
        "original": json_safe(original_payload),
        "mapping": json_safe(mapping),
        "confidence": confidence,
        "source": source_name,
        "source_type": source_type,
    }

    payload = {
        "entity_id": entity_id,
        "entity_type": "asset",
        "entity_name": canonical.get("asset_name"),
        "location": canonical.get("location"),
        "status": canonical.get("status"),
        "source_id": source_id,
        "attributes": json.dumps(attributes),
        "created_at": utc_now(),
        "updated_at": canonical.get("last_updated") or utc_now(),
    }

    existing = existing_entity(entity_id)

    if existing:
        old_time = existing.get("updated_at")
        new_time = canonical.get("last_updated")

        if old_time is not None and new_time is not None:
            try:
                old_ts = pd.to_datetime(old_time)
                new_ts = pd.to_datetime(new_time)

                if (
                    pd.notna(old_ts)
                    and pd.notna(new_ts)
                    and new_ts < old_ts
                ):
                    return "SKIPPED_OLDER"
            except Exception:
                pass

        payload.pop("created_at", None)

        execute_update_by_id(
            "entities",
            "entity_id",
            entity_id,
            payload,
        )

        return "UPDATED"

    execute_insert(
        "entities",
        payload,
    )

    return "INSERTED"


def persist_entity_data(
    entity_id: str,
    canonical: dict[str, Any],
    original_payload: dict[str, Any],
    source_id: str,
) -> None:
    if engine is None or not table_columns("entity_data"):
        return

    payload = {
        "id": uuid.uuid4(),
        "entity_id": entity_id,
        "source_id": source_id,
        "canonical_data": json.dumps(
            json_safe(canonical)
        ),
        "original_data": json.dumps(
            json_safe(original_payload)
        ),
        "captured_at": canonical.get("last_updated") or utc_now(),
        "created_at": utc_now(),
    }

    try:
        execute_insert(
            "entity_data",
            payload,
        )
    except Exception:
        payload.pop("id", None)
        try:
            execute_insert(
                "entity_data",
                payload,
            )
        except Exception:
            pass


def persist_event(
    entity_id: str,
    source_id: str,
    event_type: str,
    location: str | None,
    metadata: dict[str, Any],
    occurred_at: Any = None,
) -> None:
    if engine is None or not table_columns("events"):
        return

    payload = {
        "event_id": uuid.uuid4(),
        "entity_id": entity_id,
        "source_id": source_id,
        "event_type": event_type,
        "actor_id": "octopus-agent",
        "actor_type": "system",
        "location": location,
        "occurred_at": occurred_at or utc_now(),
        "event_metadata": json.dumps(
            json_safe(metadata)
        ),
        "created_at": utc_now(),
    }

    try:
        execute_insert(
            "events",
            payload,
        )
    except Exception:
        payload.pop("event_id", None)
        try:
            execute_insert(
                "events",
                payload,
            )
        except Exception:
            pass


def record_sync_run(
    source_id: str,
    source_name: str,
    total_rows: int,
    valid_rows: int,
    invalid_rows: int,
    inserted: int,
    updated: int,
    conflicts: int,
    mapping: dict[str, str],
    status: str,
    error_message: str | None = None,
) -> None:
    if engine is None or not table_columns("sync_runs"):
        return

    payload = {
        "sync_run_id": uuid.uuid4(),
        "source_id": source_id,
        "source_name": source_name,
        "started_at": utc_now(),
        "completed_at": utc_now(),
        "status": status,
        "rows_processed": total_rows,
        "rows_valid": valid_rows,
        "rows_invalid": invalid_rows,
        "inserted_count": inserted,
        "updated_count": updated,
        "conflict_count": conflicts,
        "mapping": json.dumps(
            json_safe(mapping)
        ),
        "error_message": error_message,
    }

    try:
        execute_insert(
            "sync_runs",
            payload,
        )
    except Exception:
        payload.pop("sync_run_id", None)
        try:
            execute_insert(
                "sync_runs",
                payload,
            )
        except Exception:
            pass


# ============================================================
# MAIN FILE INGESTION PIPELINE
# ============================================================

def ingest_file(
    path: Path,
    source_key: str,
    connector_type: str,
    mapping_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    if engine is None:
        raise RuntimeError(
            "PostgreSQL is not configured. "
            "Set DATABASE_URL in .env."
        )

    frame = extract_dataframe(
        path,
        connector_type,
    )

    if frame.empty:
        raise ValueError(
            "Source contains no rows."
        )

    inspection = detect_mapping(frame)

    mapping = dict(
        mapping_override
        or inspection["mapping"]
    )

    if mapping_override:
        frame_columns = {
            str(column)
            for column in frame.columns
        }
        mapping = {
            str(canonical): str(source_column)
            for canonical, source_column
            in mapping_override.items()
            if str(source_column) in frame_columns
        }

    missing_fields = [
        field
        for field in CANONICAL_FIELDS
        if field not in mapping
    ]

    if missing_fields:
        raise ValueError(
            "Schema mapping is incomplete. "
            "Missing canonical fields: "
            + ", ".join(missing_fields)
        )

    normalized = normalize_dataframe(
        frame,
        mapping,
    )

    validation = validate_dataframe(
        normalized
    )

    source_name = path.name
    source_type = (
        connector_type.upper()
        if connector_type
        else path.suffix.upper().lstrip(".")
    )

    upsert_source(
        source_key,
        source_name,
        source_type,
        {
            "path": str(path),
            "rows": len(frame),
            "mapping": mapping,
        },
    )

    inserted = 0
    updated = 0
    conflicts = 0
    invalid = 0
    event_counts: dict[str, int] = {}
    digital_records: list[dict[str, Any]] = []

    for index, row in normalized.iterrows():
        canonical = {
            key: json_safe(value)
            for key, value in row.to_dict().items()
        }

        original = {
            str(key): json_safe(value)
            for key, value in frame.iloc[index].to_dict().items()
        }

        errors = validation["row_results"][index]["errors"]

        if errors:
            invalid += 1
            continue

        identity_seed = (
            f"{source_key}|"
            f"{canonical.get('asset_id')}"
        )

        entity_id = (
            "asset:"
            + stable_hash(identity_seed)
        )

        confidence_values = []

        for canonical_field, source_column in mapping.items():
            try:
                confidence_values.append(
                    mapping_confidence(
                        source_column,
                        canonical_field,
                        frame,
                    )
                )
            except Exception:
                pass

        confidence = (
            round(
                sum(confidence_values)
                / len(confidence_values),
                2,
            )
            if confidence_values
            else 0.0
        )

        result = persist_entity(
            entity_id,
            canonical,
            source_key,
            source_name,
            source_type,
            original,
            mapping,
            confidence,
        )

        if result == "INSERTED":
            inserted += 1
            event_type = "ENTITY_CREATED"
        elif result == "UPDATED":
            updated += 1
            event_type = "ENTITY_UPDATED"
        elif result == "SKIPPED_OLDER":
            conflicts += 1
            event_type = "CONFLICT_OLDER_SOURCE_SKIPPED"
        else:
            event_type = "ENTITY_PROCESSED"

        event_counts[event_type] = (
            event_counts.get(event_type, 0)
            + 1
        )

        persist_entity_data(
            entity_id,
            canonical,
            original,
            source_key,
        )

        persist_event(
            entity_id,
            source_key,
            event_type,
            canonical.get("location"),
            {
                "asset_id": canonical.get("asset_id"),
                "asset_name": canonical.get("asset_name"),
                "status": canonical.get("status"),
                "last_updated": canonical.get("last_updated"),
                "source": source_name,
                "confidence": confidence,
            },
            canonical.get("last_updated") or utc_now(),
        )

        digital_records.append(
            {
                "entity_id": entity_id,
                "canonical": canonical,
                "original": original,
                "source": source_name,
                "source_type": source_type,
                "confidence": confidence,
            }
        )

    status = (
        "SUCCESS"
        if invalid == 0
        else "PARTIAL"
    )

    record_sync_run(
        source_key,
        source_name,
        len(normalized),
        validation["valid_rows"],
        validation["invalid_rows"],
        inserted,
        updated,
        conflicts,
        mapping,
        status,
    )

    return {
        "success": True,
        "stage": "central_database",
        "source_key": source_key,
        "source_name": source_name,
        "connector_type": connector_type,
        "rows_processed": len(normalized),
        "valid_rows": validation["valid_rows"],
        "invalid_rows": validation["invalid_rows"],
        "inserted": inserted,
        "updated": updated,
        "conflicts": conflicts,
        "duplicate_asset_ids": validation["duplicate_asset_ids"],
        "mapping": mapping,
        "mapping_confidence": inspection["candidates"],
        "event_counts": event_counts,
        "digital_records": digital_records,
        "message": (
            "Source processed through the Octopus "
            "ingestion pipeline and synchronized to PostgreSQL."
        ),
    }


# ============================================================
# FILE CONNECT / SCHEMA REVIEW
# ============================================================

def save_uploaded_file(
    file: UploadFile,
) -> Path:
    suffix = (
        Path(file.filename or "source")
        .suffix
        .lower()
    )

    if suffix not in SUPPORTED_LOCAL_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Supported formats: CSV, XLS, XLSX, JSON, "
                "JSONL, NDJSON, XML, YAML and YML."
            ),
        )

    safe_name = Path(
        file.filename or "source"
    ).name

    target = (
        IMPORT_DIR
        / f"{uuid.uuid4().hex}_{safe_name}"
    )

    with target.open("wb") as output:
        shutil.copyfileobj(
            file.file,
            output,
        )

    return target


def inspect_source(
    path: Path,
    connector_type: str | None = None,
) -> dict[str, Any]:
    frame = extract_dataframe(
        path,
        connector_type,
    )

    mapping = detect_mapping(
        frame
    )

    preview = []

    for _, row in frame.head(5).iterrows():
        preview.append(
            {
                str(key): json_safe(value)
                for key, value
                in row.to_dict().items()
            }
        )

    return {
        "columns": [
            str(column)
            for column in frame.columns
        ],
        "column_count": len(frame.columns),
        "mapping": mapping["mapping"],
        "mapping_details": mapping["candidates"],
        "complete": mapping["complete"],
        "preview": preview,
        "rows_previewed": len(preview),
        "total_rows": len(frame),
    }


@app.post("/api/connect/file")
async def connect_file(
    file: UploadFile = File(...),
    connector_type: str = Form("file"),
):
    path = save_uploaded_file(file)

    try:
        inspection = inspect_source(
            path,
            connector_type,
        )

        return {
            "success": True,
            "stage": "schema_mapping",
            "connector_type": connector_type,
            "source_file": str(path),
            "source_name": path.name,
            "inspection": inspection,
            "mapping": inspection["mapping"],
        }

    except Exception as exc:
        return {
            "success": False,
            "stage": "inspection",
            "message": str(exc),
            "source_file": str(path),
            "source_name": path.name,
        }


@app.post("/api/schema/approve")
async def approve_schema(
    source_file: str = Form(...),
    mapping_json: str = Form(...),
):
    try:
        mapping = json.loads(mapping_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid mapping JSON.",
        )

    if not isinstance(mapping, dict):
        raise HTTPException(
            status_code=400,
            detail="Mapping must be a JSON object.",
        )

    path = Path(source_file).resolve()

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Source file not found.",
        )

    APPROVED_MAPPING_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    APPROVED_MAPPING_FILE.write_text(
        json.dumps(mapping, indent=2),
        encoding="utf-8",
    )

    suffix = path.suffix.lower()

    if suffix == ".csv":
        connector_type = "csv"
    elif suffix in {".xls", ".xlsx"}:
        connector_type = "excel"
    else:
        connector_type = "file"

    result = ingest_file(
        path,
        f"manual:{stable_hash(str(path))}",
        connector_type,
        mapping,
    )

    result["stage"] = "approved_and_synchronized"
    return result


# ============================================================
# AUTOMATIC AGENT FILE SYNC
# ============================================================

@app.post("/api/sync/file")
async def sync_file(
    file: UploadFile = File(...),
    source_key: str = Form(
        "LOCAL-AUTHORIZED-SOURCE"
    ),
    connector_type: str = Form("file"),
    mapping_json: str = Form("{}"),
):
    path = save_uploaded_file(file)

    try:
        mapping = json.loads(
            mapping_json
        ) if mapping_json else {}

        if not isinstance(mapping, dict):
            mapping = {}

        if connector_type in {
            "",
            "file",
            "auto",
        }:
            suffix = path.suffix.lower()

            if suffix == ".csv":
                connector_type = "csv"
            elif suffix in {".xls", ".xlsx"}:
                connector_type = "excel"
            else:
                connector_type = (
                    suffix.lstrip(".")
                    or "file"
                )

        result = ingest_file(
            path,
            source_key,
            connector_type,
            mapping or None,
        )

        return result

    except Exception as exc:
        try:
            record_sync_run(
                source_key,
                path.name,
                0,
                0,
                0,
                0,
                0,
                0,
                {},
                "FAILED",
                str(exc),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Octopus ingestion failed: {exc}",
        )


# ============================================================
# REMOTE SOURCE SYNC
# Google Sheets / API JSON
# ============================================================

@app.post("/api/sync/url")
def sync_url(
    payload: dict[str, Any],
):
    url = str(
        payload.get("url", "")
    ).strip()

    source_type = str(
        payload.get(
            "source_type",
            "api",
        )
    ).strip()

    source_key = str(
        payload.get(
            "source_key",
            stable_hash(url),
        )
    )

    mapping_override = payload.get(
        "mapping"
    )

    if not url:
        raise HTTPException(
            status_code=400,
            detail="A source URL is required.",
        )

    try:
        frame, metadata = read_source(
            url,
            source_type=source_type,
        )

        if frame.empty:
            raise ValueError(
                "Remote source returned no rows."
            )

        inspection = detect_mapping(
            frame
        )

        mapping = (
            dict(mapping_override)
            if isinstance(
                mapping_override,
                dict,
            )
            else dict(
                inspection["mapping"]
            )
        )

        missing = [
            field
            for field in CANONICAL_FIELDS
            if field not in mapping
        ]

        if missing:
            raise ValueError(
                "Remote source schema mapping is incomplete. "
                "Missing: "
                + ", ".join(missing)
            )

        normalized = normalize_dataframe(
            frame,
            mapping,
        )

        validation = validate_dataframe(
            normalized
        )

        source_name = (
            "Google Sheet"
            if source_type == "google_sheets"
            else url
        )

        upsert_source(
            source_key,
            source_name,
            source_type.upper(),
            {
                "url": url,
                "rows": len(frame),
                "mapping": mapping,
                "reader_metadata": metadata,
            },
        )

        inserted = 0
        updated = 0
        conflicts = 0
        digital_records = []

        for index, row in normalized.iterrows():
            errors = validation[
                "row_results"
            ][index]["errors"]

            if errors:
                continue

            canonical = {
                key: json_safe(value)
                for key, value
                in row.to_dict().items()
            }

            original = {
                str(key): json_safe(value)
                for key, value
                in frame.iloc[index]
                .to_dict()
                .items()
            }

            entity_id = (
                "asset:"
                + stable_hash(
                    f"{source_key}|{canonical.get('asset_id')}"
                )
            )

            confidence_values = []

            for canonical_field, source_column in mapping.items():
                try:
                    confidence_values.append(
                        mapping_confidence(
                            source_column,
                            canonical_field,
                            frame,
                        )
                    )
                except Exception:
                    pass

            confidence = (
                round(
                    sum(confidence_values)
                    / len(confidence_values),
                    2,
                )
                if confidence_values
                else 0.0
            )

            result = persist_entity(
                entity_id,
                canonical,
                source_key,
                source_name,
                source_type,
                original,
                mapping,
                confidence,
            )

            if result == "INSERTED":
                inserted += 1
                event_type = "ENTITY_CREATED"
            elif result == "UPDATED":
                updated += 1
                event_type = "ENTITY_UPDATED"
            elif result == "SKIPPED_OLDER":
                conflicts += 1
                event_type = (
                    "CONFLICT_OLDER_SOURCE_SKIPPED"
                )
            else:
                event_type = "ENTITY_PROCESSED"

            persist_entity_data(
                entity_id,
                canonical,
                original,
                source_key,
            )

            persist_event(
                entity_id,
                source_key,
                event_type,
                canonical.get("location"),
                {
                    "source": source_name,
                    "url": url,
                    "canonical": canonical,
                },
                canonical.get("last_updated")
                or utc_now(),
            )

            digital_records.append(
                {
                    "entity_id": entity_id,
                    "canonical": canonical,
                    "original": original,
                    "source": source_name,
                    "source_type": source_type,
                    "confidence": confidence,
                }
            )

        record_sync_run(
            source_key,
            source_name,
            len(normalized),
            validation["valid_rows"],
            validation["invalid_rows"],
            inserted,
            updated,
            conflicts,
            mapping,
            (
                "SUCCESS"
                if validation["invalid_rows"] == 0
                else "PARTIAL"
            ),
        )

        return {
            "success": True,
            "stage": "central_database",
            "source_type": source_type,
            "source": url,
            "rows_processed": len(normalized),
            "valid_rows": validation["valid_rows"],
            "invalid_rows": validation["invalid_rows"],
            "inserted": inserted,
            "updated": updated,
            "conflicts": conflicts,
            "mapping": mapping,
            "mapping_confidence": inspection[
                "candidates"
            ],
            "digital_records": digital_records,
            "message": (
                "Remote source processed and synchronized "
                "to PostgreSQL."
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Remote source ingestion failed: "
                f"{exc}"
            ),
        )


# ============================================================
# COMPUTER INVENTORY
# ============================================================

def computer_entity_from_item(
    item: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    path_value = str(
        item.get("path", "")
    )

    name = str(
        item.get(
            "name",
            Path(path_value).name
            or "Unknown file",
        )
    )

    extension = str(
        item.get(
            "extension",
            Path(name).suffix,
        )
    )

    file_type = str(
        item.get(
            "type",
            extension.lstrip(".")
            or "file",
        )
    )

    drive = str(
        item.get(
            "drive",
            "",
        )
    )

    modified_at = item.get(
        "modified_at"
    )

    return {
        "entity_id": computer_entity_id(
            path_value
        ),
        "entity_type": "computer_file",
        "entity_name": name,
        "location": path_value,
        "status": "Discovered",
        "source_id": computer_source_id(data),
        "attributes": {
            "source": "Local Computer",
            "computer_name": data.get(
                "computer_name",
                "unknown",
            ),
            "path": path_value,
            "file_name": name,
            "extension": extension,
            "file_type": file_type,
            "drive": drive,
            "size_bytes": int(
                item.get(
                    "size_bytes",
                    0,
                )
                or 0
            ),
            "modified_at": modified_at,
            "data_source": bool(
                item.get(
                    "data_source",
                    False,
                )
            ),
            "original": dict(item),
        },
        "created_at": modified_at,
        "updated_at": modified_at,
    }


def computer_entities(
    q: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    data = read_inventory()
    files = data.get("files", [])
    term = q.lower().strip() if q else ""
    rows = []

    for item in files:
        row = computer_entity_from_item(
            item,
            data,
        )

        if term:
            searchable = " ".join([
                str(row.get("entity_id", "")),
                str(row.get("entity_name", "")),
                str(row.get("location", "")),
                str(row.get("status", "")),
                str(row.get("source_id", "")),
            ]).lower()

            if term not in searchable:
                continue

        rows.append(row)

    rows.sort(
        key=lambda item: str(
            item.get("updated_at", "")
        ),
        reverse=True,
    )

    return rows[: max(1, min(int(limit), 5000))]


def get_computer_entity(
    entity_id: str,
) -> dict[str, Any] | None:
    data = read_inventory()

    for item in data.get("files", []):
        path_value = str(
            item.get("path", "")
        )

        if (
            computer_entity_id(path_value)
            == entity_id
        ):
            return computer_entity_from_item(
                item,
                data,
            )

    return None


@app.get("/api/computer/inventory")
def computer_inventory(
    q: str | None = None,
    extension: str | None = None,
    drive: str | None = None,
    limit: int = 500,
    offset: int = 0,
):
    data = read_inventory()
    files = data.get("files", [])

    if q:
        term = q.lower()
        files = [
            item
            for item in files
            if (
                term in str(
                    item.get("name", "")
                ).lower()
                or term in str(
                    item.get("path", "")
                ).lower()
                or term in str(
                    item.get("type", "")
                ).lower()
            )
        ]

    if extension:
        wanted = extension.lower()
        if not wanted.startswith("."):
            wanted = "." + wanted

        files = [
            item
            for item in files
            if str(
                item.get("extension", "")
            ).lower() == wanted
        ]

    if drive:
        wanted = drive.upper()
        files = [
            item
            for item in files
            if str(
                item.get("drive", "")
            ).upper() == wanted
        ]

    total_matching = len(files)
    safe_limit = min(
        max(limit, 1),
        2000,
    )

    page = files[offset: offset + safe_limit]

    return {
        "success": True,
        "computer_name": data.get(
            "computer_name",
            "unknown",
        ),
        "generated_at": data.get(
            "generated_at"
        ),
        "drives": data.get(
            "drives",
            [],
        ),
        "total_files": data.get(
            "total_files",
            len(files),
        ),
        "total_matching": total_matching,
        "offset": offset,
        "limit": safe_limit,
        "files": page,
    }


@app.get("/api/computer/stats")
def computer_stats():
    data = read_inventory()
    files = data.get("files", [])
    extensions: dict[str, int] = {}
    drives: dict[str, int] = {}
    structured_data = 0

    for item in files:
        extension = str(
            item.get("extension", "")
        ).lower()
        drive = str(
            item.get("drive", "")
        ).upper()

        extensions[extension] = (
            extensions.get(extension, 0)
            + 1
        )

        drives[drive] = (
            drives.get(drive, 0)
            + 1
        )

        if item.get(
            "data_source",
            False,
        ):
            structured_data += 1

    return {
        "success": True,
        "computer": data.get(
            "computer_name",
            "unknown",
        ),
        "total_files": len(files),
        "structured_data_files": structured_data,
        "extensions": dict(
            sorted(
                extensions.items(),
                key=lambda pair: pair[1],
                reverse=True,
            )
        ),
        "drives": drives,
        "generated_at": data.get(
            "generated_at"
        ),
    }


# ============================================================
# SYNC STATUS
# ============================================================

@app.get("/api/sync/status")
def sync_status():
    inventory = read_inventory()

    return {
        "success": True,
        "computer": inventory.get(
            "computer_name",
            "unknown",
        ),
        "inventory_files": inventory.get(
            "total_files",
            len(inventory.get("files", [])),
        ),
        "generated_at": inventory.get(
            "generated_at"
        ),
        "agent_expected": True,
        "polling_seconds": 3,
        "pipeline": (
            "Connect -> Extract -> Schema Detection -> "
            "Adaptive Mapping -> Normalize -> Validate -> "
            "Identity -> Conflict -> PostgreSQL -> Events"
        ),
        "supported_local_formats": sorted(
            SUPPORTED_LOCAL_EXTENSIONS
        ),
        "remote_sources": [
            "Google Sheets",
            "REST/API JSON",
        ],
    }


# ============================================================
# SEARCH / ENTITIES
# ============================================================

@app.get("/api/entities")
def entities(
    q: str | None = None,
    limit: int = 500,
):
    safe_limit = min(
        max(int(limit), 1),
        5000,
    )

    db_rows: list[dict[str, Any]] = []

    if (
        engine is not None
        and table_columns("entities")
    ):
        try:
            if q:
                db_rows = query_rows(
                    """
                    SELECT
                        entity_id,
                        entity_type,
                        entity_name,
                        location,
                        status,
                        source_id,
                        attributes,
                        created_at,
                        updated_at
                    FROM entities
                    WHERE CAST(entity_id AS TEXT) ILIKE :q
                       OR COALESCE(entity_name, '') ILIKE :q
                       OR COALESCE(location, '') ILIKE :q
                       OR COALESCE(status, '') ILIKE :q
                       OR COALESCE(source_id, '') ILIKE :q
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """,
                    {
                        "q": f"%{q}%",
                        "limit": safe_limit,
                    },
                )
            else:
                db_rows = query_rows(
                    """
                    SELECT
                        entity_id,
                        entity_type,
                        entity_name,
                        location,
                        status,
                        source_id,
                        attributes,
                        created_at,
                        updated_at
                    FROM entities
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """,
                    {"limit": safe_limit},
                )
        except Exception:
            db_rows = []

    computer_rows = computer_entities(
        q=q,
        limit=safe_limit,
    )

    combined = (
        jsonable_rows(db_rows)
        + computer_rows
    )

    combined.sort(
        key=lambda row: str(
            row.get("updated_at", "")
        ),
        reverse=True,
    )

    return {
        "success": True,
        "count": len(combined[:safe_limit]),
        "entities": combined[:safe_limit],
        "data_scope": (
            "PostgreSQL + live computer inventory"
        ),
    }


@app.get("/api/entities/{entity_id}")
def entity_detail(
    entity_id: str,
):
    computer_entity = get_computer_entity(
        entity_id
    )

    if computer_entity is not None:
        return {
            "success": True,
            "entity": computer_entity,
            "computer_data": True,
        }

    if (
        engine is None
        or not table_columns("entities")
    ):
        raise HTTPException(
            status_code=503,
            detail="Database unavailable.",
        )

    rows = query_rows(
        """
        SELECT
            entity_id,
            entity_type,
            entity_name,
            location,
            status,
            source_id,
            attributes,
            created_at,
            updated_at
        FROM entities
        WHERE entity_id = :entity_id
        LIMIT 1
        """,
        {"entity_id": entity_id},
    )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Entity not found.",
        )

    return {
        "success": True,
        "entity": jsonable_rows(rows)[0],
        "computer_data": False,
    }


# ============================================================
# EVENTS
# ============================================================

@app.get("/api/entities/{entity_id}/events")
def entity_events(
    entity_id: str,
):
    computer_entity = get_computer_entity(
        entity_id
    )

    if computer_entity is not None:
        original = computer_entity[
            "attributes"
        ]["original"]

        return {
            "success": True,
            "events": [
                {
                    "event_id": (
                        f"{entity_id}:discovered"
                    ),
                    "entity_id": entity_id,
                    "source_id": computer_entity[
                        "source_id"
                    ],
                    "event_type": (
                        "COMPUTER_FILE_DISCOVERED"
                    ),
                    "actor_id": "octopus-agent",
                    "actor_type": "agent",
                    "location": computer_entity[
                        "location"
                    ],
                    "occurred_at": (
                        original.get("modified_at")
                        or read_inventory().get(
                            "generated_at"
                        )
                    ),
                    "event_metadata": {
                        "file_name": computer_entity[
                            "entity_name"
                        ],
                        "path": computer_entity[
                            "location"
                        ],
                    },
                }
            ],
        }

    if (
        engine is None
        or not table_columns("events")
    ):
        return {
            "success": True,
            "events": [],
        }

    try:
        rows = query_rows(
            """
            SELECT
                event_id,
                entity_id,
                source_id,
                event_type,
                actor_id,
                actor_type,
                location,
                occurred_at,
                event_metadata
            FROM events
            WHERE entity_id = :entity_id
            ORDER BY occurred_at DESC
            LIMIT 500
            """,
            {"entity_id": entity_id},
        )

        return {
            "success": True,
            "events": jsonable_rows(rows),
        }
    except Exception as exc:
        return {
            "success": False,
            "events": [],
            "message": str(exc),
        }


@app.get("/api/events")
def all_events(
    limit: int = 200,
):
    safe_limit = min(
        max(int(limit), 1),
        1000,
    )

    rows: list[dict[str, Any]] = []

    if (
        engine is not None
        and table_columns("events")
    ):
        try:
            rows = query_rows(
                """
                SELECT
                    event_id,
                    entity_id,
                    source_id,
                    event_type,
                    actor_id,
                    actor_type,
                    location,
                    occurred_at,
                    event_metadata
                FROM events
                ORDER BY occurred_at DESC
                LIMIT :limit
                """,
                {"limit": safe_limit},
            )
        except Exception:
            rows = []

    inventory = read_inventory()
    generated_at = inventory.get(
        "generated_at"
    )

    if generated_at:
        rows.append(
            {
                "event_id": (
                    "computer-inventory-sync"
                ),
                "entity_id": None,
                "source_id": computer_source_id(
                    inventory
                ),
                "event_type": (
                    "COMPUTER_INVENTORY_SYNC"
                ),
                "actor_id": "octopus-agent",
                "actor_type": "agent",
                "location": None,
                "occurred_at": generated_at,
                "event_metadata": {
                    "computer": inventory.get(
                        "computer_name",
                        "unknown",
                    ),
                    "files": inventory.get(
                        "total_files",
                        0,
                    ),
                },
            }
        )

    rows.sort(
        key=lambda row: str(
            row.get("occurred_at", "")
        ),
        reverse=True,
    )

    return {
        "success": True,
        "events": jsonable_rows(
            rows[:safe_limit]
        ),
    }


# ============================================================
# SOURCES
# ============================================================

@app.get("/api/sources")
def sources():
    rows: list[dict[str, Any]] = []

    if (
        engine is not None
        and table_columns("sources")
    ):
        try:
            rows = query_rows(
                """
                SELECT
                    source_id,
                    source_name,
                    source_type,
                    status,
                    last_sync_at,
                    created_at
                FROM sources
                ORDER BY created_at DESC
                LIMIT 1000
                """
            )
        except Exception:
            rows = []

    inventory = read_inventory()

    local_source = {
        "source_id": computer_source_id(
            inventory
        ),
        "source_name": (
            "Local Computer — "
            + str(
                inventory.get(
                    "computer_name",
                    "unknown",
                )
            )
        ),
        "source_type": "COMPUTER_INVENTORY",
        "status": (
            "ONLINE"
            if inventory.get("success")
            else "WAITING"
        ),
        "last_sync_at": inventory.get(
            "generated_at"
        ),
        "created_at": inventory.get(
            "generated_at"
        ),
    }

    combined = [
        local_source
    ] + jsonable_rows(rows)

    seen = set()
    unique = []

    for source in combined:
        source_id = str(
            source.get("source_id")
        )

        if source_id in seen:
            continue

        seen.add(source_id)
        unique.append(source)

    return {
        "success": True,
        "sources": unique,
        "computer_source": local_source,
    }


# ============================================================
# LOCATIONS
# ============================================================

@app.get("/api/locations")
def locations():
    inventory = read_inventory()
    files = inventory.get("files", [])
    drives: dict[str, int] = {}
    roots: dict[str, int] = {}

    for item in files:
        drive = str(
            item.get("drive", "")
        ).upper()
        path_value = str(
            item.get("path", "")
        )

        if drive:
            drives[drive] = (
                drives.get(drive, 0)
                + 1
            )

        if path_value:
            root = (
                Path(path_value).anchor
                or drive
            )
            roots[str(root)] = (
                roots.get(str(root), 0)
                + 1
            )

    return {
        "success": True,
        "computer": inventory.get(
            "computer_name",
            "unknown",
        ),
        "drives": drives,
        "roots": roots,
        "files": len(files),
    }


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/api/dashboard")
def dashboard():
    inventory = read_inventory()
    db_entities = 0
    db_sources = 0
    db_events = 0

    if engine is not None:
        try:
            db_entities = int(
                query_rows(
                    "SELECT COUNT(*) AS c FROM entities"
                )[0]["c"]
            )
        except Exception:
            pass

        try:
            db_sources = int(
                query_rows(
                    "SELECT COUNT(*) AS c FROM sources"
                )[0]["c"]
            )
        except Exception:
            pass

        try:
            db_events = int(
                query_rows(
                    "SELECT COUNT(*) AS c FROM events"
                )[0]["c"]
            )
        except Exception:
            pass

    return {
        "success": True,
        "computer": inventory.get(
            "computer_name",
            "unknown",
        ),
        "computer_files": len(
            inventory.get("files", [])
        ),
        "computer_structured_data": sum(
            1
            for item in inventory.get("files", [])
            if item.get("data_source", False)
        ),
        "database_entities": db_entities,
        "database_sources": db_sources,
        "database_events": db_events,
        "total_entities_visible": (
            len(
                inventory.get("files", [])
            )
            + db_entities
        ),
        "generated_at": inventory.get(
            "generated_at"
        ),
    }


# ============================================================
# COMPUTER CONNECTOR
# ============================================================

@app.get("/api/connect/computer")
def connect_computer():
    data = read_inventory()

    if not data.get("success"):
        return {
            "success": False,
            "stage": "computer_waiting",
            "message": (
                "Computer inventory is not available yet. "
                "Start agent.py."
            ),
        }

    files = data.get("files", [])
    structured = [
        item
        for item in files
        if item.get("data_source", False)
    ]

    return {
        "success": True,
        "stage": "computer_connected",
        "connector_type": "computer",
        "source_name": (
            "Local Computer — "
            + str(
                data.get(
                    "computer_name",
                    "unknown",
                )
            )
        ),
        "source_key": computer_source_id(data),
        "inspection": {
            "computer_name": data.get(
                "computer_name",
                "unknown",
            ),
            "total_files": len(files),
            "structured_data_files": len(structured),
            "drives": data.get(
                "drives",
                [],
            ),
        },
        "message": (
            "Live computer data connected to Project Octopus."
        ),
    }


# ============================================================
# CONNECTOR STATUS ENDPOINTS
# ============================================================

@app.post("/api/connect/mysql")
def connect_mysql(
    payload: dict[str, Any],
):
    return {
        "success": False,
        "message": (
            "MySQL connector requires an authorized reachable "
            "MySQL source."
        ),
        "received": {
            "host": payload.get("host"),
            "port": payload.get("port"),
            "database": payload.get("database"),
        },
    }


@app.post("/api/connect/api")
def connect_api(
    payload: dict[str, Any],
):
    return {
        "success": True,
        "message": (
            "API source can be synchronized through /api/sync/url "
            "when the authorized endpoint returns JSON."
        ),
        "url": payload.get("url"),
    }


@app.post("/api/connect/sheets")
def connect_sheets(
    payload: dict[str, Any],
):
    return {
        "success": True,
        "message": (
            "Google Sheets source can be synchronized through "
            "/api/sync/url after authorized access is provided."
        ),
        "reference": payload.get("reference"),
        "source_type": "google_sheets",
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
