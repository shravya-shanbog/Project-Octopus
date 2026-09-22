from __future__ import annotations

import json
import mimetypes
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, text


# ============================================================
# PROJECT OCTOPUS
# BACKEND API + COMPUTER INVENTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
IMPORT_DIR = DATA_DIR / "imports"

INVENTORY_FILE = DATA_DIR / "computer_inventory.json"
APPROVED_MAPPING_FILE = (
    BASE_DIR / "agent" / "approved_mapping.json"
)

load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )
else:
    engine = None


app = FastAPI(
    title="Project Octopus",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STATIC WEBSITE
# ============================================================

if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup() -> None:
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if engine is not None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS computer_sync_status (
                            id INTEGER PRIMARY KEY,
                            computer_name TEXT,
                            total_files INTEGER NOT NULL DEFAULT 0,
                            generated_at TEXT,
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
# HELPERS
# ============================================================

def read_inventory() -> dict[str, Any]:
    if not INVENTORY_FILE.exists():
        return {
            "success": False,
            "computer_name": "unknown",
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
            "total_files": 0,
            "files": [],
            "error": str(exc),
        }


def safe_json_value(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def detect_mapping(columns: list[str]) -> dict[str, str]:
    """
    Lightweight adaptive mapping used by the source-inspection API.

    Existing full processing modules remain separate in processing/.
    """

    aliases = {
        "asset_id": [
            "asset_id",
            "asset no",
            "asset_no",
            "asset number",
            "id",
            "device_no",
            "device no",
            "equipment id",
            "equipment_id",
            "machine id",
        ],
        "asset_name": [
            "asset_name",
            "asset name",
            "name",
            "machine_desc",
            "machine desc",
            "description",
            "equipment",
            "device",
        ],
        "location": [
            "location",
            "place",
            "site_loc",
            "site loc",
            "current location",
            "current_location",
            "site",
        ],
        "status": [
            "status",
            "condition",
            "state",
        ],
        "last_updated": [
            "last_updated",
            "last updated",
            "modified",
            "modified_at",
            "updated",
            "updated_at",
            "timestamp",
        ],
    }

    normalized = {
        str(column).strip().lower(): str(column)
        for column in columns
    }

    mapping: dict[str, str] = {}

    for canonical, names in aliases.items():
        for name in names:
            if name in normalized:
                mapping[canonical] = normalized[name]
                break

    return mapping


def save_uploaded_file(
    file: UploadFile,
) -> Path:
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only CSV, XLSX and XLS are supported "
                "by the file ingestion endpoint."
            ),
        )

    target = (
        IMPORT_DIR
        / f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    )

    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    return target


def inspect_tabular_file(
    path: Path,
) -> dict[str, Any]:
    suffix = path.suffix.lower()

    if suffix == ".csv":
        frame = pd.read_csv(
            path,
            nrows=10,
        )
    else:
        frame = pd.read_excel(
            path,
            nrows=10,
        )

    columns = [
        str(column)
        for column in frame.columns
    ]

    mapping = detect_mapping(columns)

    preview = []
    for _, row in frame.head(5).iterrows():
        preview.append({
            str(k): safe_json_value(v)
            for k, v in row.to_dict().items()
        })

    return {
        "columns": columns,
        "column_count": len(columns),
        "mapping": mapping,
        "preview": preview,
        "rows_previewed": len(preview),
    }


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

        return [
            dict(row._mapping)
            for row in result
        ]


def jsonable_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output = []

    for row in rows:
        cleaned = {}

        for key, value in row.items():
            if isinstance(value, (dict, list)):
                cleaned[key] = value
            else:
                try:
                    json.dumps(value)
                    cleaned[key] = value
                except Exception:
                    cleaned[key] = str(value)

        output.append(cleaned)

    return output


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():
    index = FRONTEND_DIR / "index.html"

    if index.exists():
        return FileResponse(index)

    return {
        "project": "Project Octopus",
        "status": "online",
        "message": "Backend running",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "success": True,
        "project": "Project Octopus",
        "backend": "online",
    }


# ============================================================
# DATABASE TEST
# ============================================================

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
# LOGIN
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
# COMPUTER INVENTORY
# ============================================================

@app.get("/api/computer/inventory")
def computer_inventory(
    q: str | None = None,
    extension: str | None = None,
    drive: str | None = None,
    limit: int = 500,
    offset: int = 0,
):
    data = read_inventory()

    files = data.get(
        "files",
        [],
    )

    if q:
        term = q.lower()

        files = [
            item
            for item in files
            if (
                term in str(item.get("name", "")).lower()
                or term in str(item.get("path", "")).lower()
                or term in str(item.get("type", "")).lower()
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
        wanted_drive = drive.upper()

        files = [
            item
            for item in files
            if str(
                item.get("drive", "")
            ).upper() == wanted_drive
        ]

    total_matching = len(files)

    page = files[
        offset : offset + min(limit, 2000)
    ]

    return {
        "success": True,
        "computer_name":
            data.get(
                "computer_name",
                "unknown",
            ),
        "generated_at":
            data.get(
                "generated_at",
            ),
        "drives":
            data.get(
                "drives",
                [],
            ),
        "total_files":
            data.get(
                "total_files",
                len(files),
            ),
        "total_matching":
            total_matching,
        "offset":
            offset,
        "limit":
            limit,
        "files":
            page,
    }


@app.get("/api/computer/stats")
def computer_stats():
    data = read_inventory()

    files = data.get(
        "files",
        [],
    )

    extensions: dict[str, int] = {}
    drives: dict[str, int] = {}
    data_sources = 0

    for item in files:

        ext = str(
            item.get(
                "extension",
                "",
            )
        ).lower()

        drive = str(
            item.get(
                "drive",
                "",
            )
        ).upper()

        extensions[ext] = (
            extensions.get(ext, 0)
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
            data_sources += 1

    return {
        "success": True,
        "computer":
            data.get(
                "computer_name",
                "unknown",
            ),
        "total_files":
            len(files),
        "structured_data_files":
            data_sources,
        "extensions":
            dict(
                sorted(
                    extensions.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ),
        "drives":
            drives,
        "generated_at":
            data.get(
                "generated_at",
            ),
    }


# ============================================================
# COMPUTER DATA WEB PAGE
# ============================================================

@app.get(
    "/computer-data",
    response_class=HTMLResponse,
)
def computer_data_page():

    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Project Octopus - Computer Data</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {
    font-family: Arial, sans-serif;
    margin: 0;
    background: #f4f7fb;
    color: #1f2937;
}
header {
    background: #14213d;
    color: white;
    padding: 20px 28px;
}
h1 {
    margin: 0 0 6px 0;
}
.controls {
    padding: 18px 28px;
    background: white;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    position: sticky;
    top: 0;
}
input, select, button {
    padding: 10px 12px;
    border: 1px solid #ccd4df;
    border-radius: 8px;
}
button {
    background: #1677c8;
    color: white;
    cursor: pointer;
}
.stats {
    padding: 18px 28px;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}
.card {
    background: white;
    border-radius: 10px;
    padding: 15px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
    min-width: 160px;
}
.table-wrap {
    padding: 0 28px 30px 28px;
    overflow-x: auto;
}
table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}
th, td {
    border-bottom: 1px solid #e5e7eb;
    padding: 10px;
    text-align: left;
    font-size: 13px;
}
th {
    background: #eef3f8;
    position: sticky;
    top: 66px;
}
.path {
    word-break: break-all;
}
</style>
</head>

<body>

<header>
    <h1>Project Octopus</h1>
    <div>Live Computer Data Inventory</div>
</header>

<div class="controls">
    <input
        id="search"
        placeholder="Search filename or path..."
    />

    <select id="drive">
        <option value="">All drives</option>
    </select>

    <select id="extension">
        <option value="">All file types</option>
    </select>

    <button onclick="loadData()">
        Refresh
    </button>
</div>

<div class="stats">
    <div class="card">
        <b>Total files</b>
        <div id="total">-</div>
    </div>

    <div class="card">
        <b>Matching files</b>
        <div id="matching">-</div>
    </div>

    <div class="card">
        <b>Computer</b>
        <div id="computer">-</div>
    </div>

    <div class="card">
        <b>Last inventory</b>
        <div id="updated">-</div>
    </div>
</div>

<div class="table-wrap">
<table>
<thead>
<tr>
<th>Name</th>
<th>Path</th>
<th>Type</th>
<th>Size</th>
<th>Modified</th>
<th>Data Source</th>
</tr>
</thead>
<tbody id="rows"></tbody>
</table>
</div>

<script>

let timer = null;

async function loadStats() {
    const response =
        await fetch("/api/computer/stats");

    const data =
        await response.json();

    document.getElementById("total")
        .textContent =
        data.total_files ?? 0;

    const extension =
        document.getElementById("extension");

    if (extension.options.length === 1) {
        Object.keys(
            data.extensions || {}
        ).forEach(function(ext) {
            const option =
                document.createElement("option");

            option.value = ext;
            option.textContent = ext;

            extension.appendChild(option);
        });
    }

    const drive =
        document.getElementById("drive");

    if (drive.options.length === 1) {
        Object.keys(
            data.drives || {}
        ).forEach(function(item) {
            const option =
                document.createElement("option");

            option.value = item;
            option.textContent = item;

            drive.appendChild(option);
        });
    }

    document.getElementById("computer")
        .textContent =
        data.computer || "unknown";

    if (data.generated_at) {
        document.getElementById("updated")
            .textContent =
            new Date(
                data.generated_at * 1000
            ).toLocaleString();
    }
}


async function loadData() {

    const query =
        document.getElementById("search")
            .value.trim();

    const extension =
        document.getElementById("extension")
            .value;

    const drive =
        document.getElementById("drive")
            .value;

    const params =
        new URLSearchParams();

    if (query) {
        params.set("q", query);
    }

    if (extension) {
        params.set(
            "extension",
            extension
        );
    }

    if (drive) {
        params.set(
            "drive",
            drive
        );
    }

    params.set("limit", "500");

    const response =
        await fetch(
            "/api/computer/inventory?"
            + params.toString()
        );

    const data =
        await response.json();

    document.getElementById("matching")
        .textContent =
        data.total_matching ?? 0;

    const body =
        document.getElementById("rows");

    body.innerHTML = "";

    for (
        const item of (
            data.files || []
        )
    ) {

        const row =
            document.createElement("tr");

        const modified =
            item.modified_at
                ? new Date(
                    item.modified_at * 1000
                ).toLocaleString()
                : "";

        const size =
            Number(
                item.size_bytes || 0
            );

        row.innerHTML = `
            <td>${escapeHtml(item.name || "")}</td>
            <td class="path">
                ${escapeHtml(item.path || "")}
            </td>
            <td>
                ${escapeHtml(
                    item.type || ""
                )}
            </td>
            <td>
                ${formatBytes(size)}
            </td>
            <td>${escapeHtml(modified)}</td>
            <td>
                ${
                    item.data_source
                    ? "YES"
                    : "INVENTORY"
                }
            </td>
        `;

        body.appendChild(row);
    }
}


function formatBytes(bytes) {

    if (!bytes) {
        return "0 B";
    }

    const units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ];

    let index = 0;
    let value = bytes;

    while (
        value >= 1024
        && index < units.length - 1
    ) {
        value /= 1024;
        index++;
    }

    return (
        value.toFixed(1)
        + " "
        + units[index]
    );
}


function escapeHtml(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


document.getElementById("search")
    .addEventListener(
        "keydown",
        function(event) {
            if (event.key === "Enter") {
                loadData();
            }
        }
    );


document.getElementById("extension")
    .addEventListener(
        "change",
        loadData
    );


document.getElementById("drive")
    .addEventListener(
        "change",
        loadData
    );


async function start() {

    await loadStats();
    await loadData();

    if (timer) {
        clearInterval(timer);
    }

    timer = setInterval(
        async function() {
            await loadStats();
            await loadData();
        },
        5000
    );
}


start();

</script>

</body>
</html>
"""


# ============================================================
# FILE CONNECT / INSPECTION
# ============================================================

@app.post("/api/connect/file")
async def connect_file(
    file: UploadFile = File(...),
    connector_type: str = Form("file"),
):
    path = save_uploaded_file(file)

    try:
        inspection = inspect_tabular_file(
            path
        )

        return {
            "success": True,
            "stage": "schema_mapping",
            "connector_type":
                connector_type,
            "source_file":
                str(path),
            "source_name":
                path.name,
            "inspection":
                inspection,
            "mapping":
                inspection["mapping"],
        }

    except Exception as exc:

        return {
            "success": False,
            "stage": "inspection",
            "message": str(exc),
            "source_file":
                str(path),
            "source_name":
                path.name,
        }


# ============================================================
# SCHEMA APPROVAL
# ============================================================

@app.post("/api/schema/approve")
async def approve_schema(
    source_file: str = Form(...),
    mapping_json: str = Form(...),
):
    try:
        mapping = json.loads(
            mapping_json
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid mapping JSON.",
        )

    path = Path(
        source_file
    ).resolve()

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
        json.dumps(
            mapping,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "success": True,
        "stage": "approved",
        "source_file": str(path),
        "mapping": mapping,
        "message": "Schema mapping approved.",
    }


# ============================================================
# SYNC ENDPOINT
# ============================================================

@app.post("/api/sync/file")
async def sync_file(
    file: UploadFile = File(...),
    source_key: str = Form(
        "LOCAL-AUTHORIZED-SOURCE"
    ),
    connector_type: str = Form("excel"),
    mapping_json: str = Form("{}"),
):
    path = save_uploaded_file(file)

    return {
        "success": True,
        "source_key":
            source_key,
        "connector_type":
            connector_type,
        "file":
            str(path),
        "mapping":
            (
                json.loads(mapping_json)
                if mapping_json
                else {}
            ),
        "message":
            "Synchronization source received.",
    }


# ============================================================
# CURRENT POSTGRES ENTITIES
# ============================================================

@app.get("/api/entities")
def entities(
    q: str | None = None,
    limit: int = 500,
):
    if engine is None:
        return {
            "success": False,
            "count": 0,
            "entities": [],
        }

    try:

        if q:
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
                WHERE
                    CAST(entity_id AS TEXT)
                    ILIKE :q
                    OR
                    COALESCE(entity_name, '')
                    ILIKE :q
                    OR
                    COALESCE(location, '')
                    ILIKE :q
                    OR
                    COALESCE(status, '')
                    ILIKE :q
                ORDER BY updated_at DESC
                LIMIT :limit
                """,
                {
                    "q": f"%{q}%",
                    "limit": min(
                        max(limit, 1),
                        2000,
                    ),
                },
            )

        else:
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
                ORDER BY updated_at DESC
                LIMIT :limit
                """,
                {
                    "limit": min(
                        max(limit, 1),
                        2000,
                    ),
                },
            )

        rows = jsonable_rows(rows)

        return {
            "success": True,
            "count": len(rows),
            "entities": rows,
        }

    except Exception as exc:

        return {
            "success": False,
            "count": 0,
            "entities": [],
            "message": str(exc),
        }


@app.get("/api/entities/{entity_id}")
def entity_detail(
    entity_id: str,
):
    if engine is None:
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
        {
            "entity_id":
                entity_id,
        },
    )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Entity not found.",
        )

    return {
        "success": True,
        "entity":
            jsonable_rows(rows)[0],
    }


@app.get("/api/entities/{entity_id}/events")
def entity_events(
    entity_id: str,
):
    if engine is None:
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
            {
                "entity_id":
                    entity_id,
            },
        )

        return {
            "success": True,
            "events":
                jsonable_rows(rows),
        }

    except Exception as exc:

        return {
            "success": False,
            "events": [],
            "message": str(exc),
        }


# ============================================================
# SOURCE LIST
# ============================================================

@app.get("/api/sources")
def sources():
    if engine is None:
        return {
            "success": False,
            "sources": [],
        }

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

        return {
            "success": True,
            "sources":
                jsonable_rows(rows),
        }

    except Exception as exc:

        return {
            "success": False,
            "sources": [],
            "message": str(exc),
        }


# ============================================================
# SOURCE CONNECTORS
# ============================================================

@app.post("/api/connect/mysql")
def connect_mysql(payload: dict[str, Any]):
    return {
        "success": False,
        "message": (
            "MySQL connector is available in the project "
            "connector layer but requires an authorized "
            "reachable MySQL source."
        ),
        "received": {
            "host":
                payload.get("host"),
            "port":
                payload.get("port"),
            "database":
                payload.get("database"),
        },
    }


@app.post("/api/connect/api")
def connect_api(payload: dict[str, Any]):
    return {
        "success": False,
        "message": (
            "API connector requires an approved API "
            "endpoint and authentication method."
        ),
        "url":
            payload.get("url"),
    }


@app.post("/api/connect/sheets")
def connect_sheets(payload: dict[str, Any]):
    return {
        "success": False,
        "message": (
            "Google Sheets connector requires "
            "authorized Google API access."
        ),
        "reference":
            payload.get("reference"),
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
