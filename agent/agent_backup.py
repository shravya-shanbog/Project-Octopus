from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import requests


# ============================================================
# PROJECT OCTOPUS
# DIRECT COMPUTER DISCOVERY AGENT
# ============================================================

BACKEND_URL = "http://127.0.0.1:8000"
POLL_SECONDS = 5
MAX_FILE_SIZE_MB = 100

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Computer inventory used by backend / website
INVENTORY_FILE = DATA_DIR / "computer_inventory.json"

# State used to detect changes
STATE_FILE = (
    PROJECT_ROOT
    / "agent"
    / "computer_agent_state.json"
)

# ============================================================
# ONLY THESE TYPES ARE SENT TO THE EXISTING DATA PIPELINE
# ============================================================

INGESTABLE_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
}

# ============================================================
# SYSTEM / CACHE DIRECTORIES NOT CRAWLED
# ============================================================

SKIP_DIRECTORIES = {
    "$Recycle.Bin",
    "System Volume Information",
    "Windows",
    "WinSxS",
    "Program Files",
    "Program Files (x86)",
    "ProgramData",
    "AppData",
    "Application Data",
    "Local Settings",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "site-packages",
}


# ============================================================
# LOG
# ============================================================

def log(message: str) -> None:
    print(
        f"[{time.strftime('%H:%M:%S')}] {message}",
        flush=True,
    )


# ============================================================
# FIND LOCAL DRIVES
# ============================================================

def get_local_drives() -> list[Path]:
    drives: list[Path] = []

    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:\\")

        try:
            if drive.exists():
                drives.append(drive)
        except OSError:
            continue

    return drives


DRIVES = get_local_drives()


# ============================================================
# STATE
# ============================================================

def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"files": {}}

    try:
        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {"files": {}}


def save_state(
    state: dict[str, Any]
) -> None:

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# PATH FILTER
# ============================================================

def should_skip_directory(
    name: str
) -> bool:
    return name in SKIP_DIRECTORIES


def should_skip_path(
    path: Path
) -> bool:

    return any(
        part in SKIP_DIRECTORIES
        for part in path.parts
    )


# ============================================================
# FILE HASH
# ============================================================

def calculate_hash(
    path: Path
) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# MIME TYPE
# ============================================================

def get_mime_type(
    path: Path
) -> str:

    return (
        mimetypes.guess_type(
            path.name
        )[0]
        or "unknown"
    )


# ============================================================
# COMPUTER SCAN
# ============================================================

def scan_computer() -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]]
]:

    inventory: list[dict[str, Any]] = []
    current_state: dict[str, dict[str, Any]] = {}

    for drive in DRIVES:

        log(
            f"SCANNING DRIVE: {drive}"
        )

        try:

            for root, dirs, files in os.walk(
                drive,
                topdown=True,
                followlinks=False,
            ):

                # Remove system/cache directories
                # before os.walk enters them.
                dirs[:] = [
                    directory
                    for directory in dirs
                    if not should_skip_directory(
                        directory
                    )
                ]

                root_path = Path(root)

                if should_skip_path(
                    root_path
                ):
                    dirs[:] = []
                    continue

                for filename in files:

                    path = (
                        root_path
                        / filename
                    )

                    try:
                        stat = path.stat()
                    except (
                        PermissionError,
                        FileNotFoundError,
                        OSError,
                    ):
                        continue

                    # Keep the scan responsive.
                    if (
                        stat.st_size
                        >
                        MAX_FILE_SIZE_MB
                        * 1024
                        * 1024
                    ):
                        continue

                    extension = (
                        path.suffix.lower()
                    )

                    key = str(
                        path
                    ).lower()

                    current_state[key] = {
                        "path": str(path),
                        "size": stat.st_size,
                        "modified_ns": stat.st_mtime_ns,
                        "extension": extension,
                    }

                    inventory.append({
                        "name": path.name,
                        "path": str(path),
                        "drive": path.drive,
                        "extension": extension,
                        "mime_type": get_mime_type(path),
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "data_source": (
                            extension
                            in INGESTABLE_EXTENSIONS
                        ),
                    })

        except (
            PermissionError,
            OSError,
        ) as exc:

            log(
                f"ACCESS SKIPPED: "
                f"{drive} | {exc}"
            )

    return inventory, current_state


# ============================================================
# SAVE COMPUTER INVENTORY
# ============================================================

def save_inventory(
    inventory: list[dict[str, Any]]
) -> None:

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "project": "Project Octopus",
        "computer_name": os.environ.get(
            "COMPUTERNAME",
            "unknown",
        ),
        "generated_at": time.time(),
        "generated_at_readable": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "drives": [
            str(drive)
            for drive in DRIVES
        ],
        "total_files": len(inventory),
        "files": inventory,
    }

    INVENTORY_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )

    log(
        f"COMPUTER INVENTORY UPDATED: "
        f"{len(inventory)} FILES"
    )


# ============================================================
# SEND ONLY CSV / EXCEL TO EXISTING OCTOPUS PIPELINE
# ============================================================

def send_data_to_backend(
    path: Path
) -> bool:

    extension = path.suffix.lower()

    # IMPORTANT:
    # JSON and arbitrary files are NOT sent here.
    if extension not in INGESTABLE_EXTENSIONS:
        return False

    mime_type = get_mime_type(path)

    log(
        f"INGESTING DATA SOURCE: {path}"
    )

    try:

        with path.open("rb") as file:

            response = requests.post(
                f"{BACKEND_URL}/api/connect/file",
                files={
                    "file": (
                        path.name,
                        file,
                        mime_type,
                    )
                },
                timeout=120,
            )

    except requests.RequestException as exc:

        log(
            f"BACKEND CONNECTION ERROR: "
            f"{exc}"
        )

        return False

    if response.ok:

        log(
            f"INGESTION SUCCESS: "
            f"{path.name}"
        )

        return True

    log(
        f"INGESTION FAILED: "
        f"{path.name} | "
        f"HTTP {response.status_code}"
    )

    return False


# ============================================================
# PROCESS NEW / CHANGED DATA SOURCES
# ============================================================

def process_changes(
    old_state: dict[str, Any],
    new_state: dict[str, dict[str, Any]],
) -> None:

    old_files = old_state.get(
        "files",
        {}
    )

    for key, current in new_state.items():

        extension = current[
            "extension"
        ]

        # Ignore JSON, PDF, images, EXE, DLL, etc.
        # They remain visible in the inventory only.
        if extension not in INGESTABLE_EXTENSIONS:
            continue

        previous = old_files.get(
            key
        )

        is_new = (
            previous is None
        )

        is_changed = (
            previous is not None
            and (
                previous.get("size")
                != current.get("size")
                or
                previous.get("modified_ns")
                != current.get("modified_ns")
            )
        )

        if not is_new and not is_changed:
            continue

        path = Path(
            current["path"]
        )

        if not path.exists():
            continue

        # Make sure a file is not being written.
        try:

            size_1 = path.stat().st_size

            time.sleep(0.5)

            size_2 = path.stat().st_size

            if size_1 != size_2:

                log(
                    f"FILE STILL CHANGING: "
                    f"{path}"
                )

                continue

        except (
            PermissionError,
            FileNotFoundError,
            OSError,
        ):
            continue

        if is_new:
            log(
                f"NEW DATA SOURCE: "
                f"{path}"
            )
        else:
            log(
                f"CHANGED DATA SOURCE: "
                f"{path}"
            )

        send_data_to_backend(
            path
        )


# ============================================================
# MAIN LOOP
# ============================================================

def main() -> None:

    log("=" * 70)
    log("PROJECT OCTOPUS")
    log("DIRECT COMPUTER DATA DISCOVERY AGENT")
    log("=" * 70)

    log(
        "BACKEND: "
        f"{BACKEND_URL}"
    )

    log(
        "DRIVES: "
        +
        ", ".join(
            str(drive)
            for drive in DRIVES
        )
    )

    log(
        f"POLLING: {POLL_SECONDS} SECONDS"
    )

    log(
        "NO MANUAL FILE UPLOAD REQUIRED"
    )

    log(
        "COMPUTER INVENTORY: ENABLED"
    )

    log(
        "CSV / XLS / XLSX AUTO-INGESTION: ENABLED"
    )

    log(
        "OTHER FILE TYPES: INVENTORY ONLY"
    )

    log("=" * 70)

    state = load_state()

    while True:

        cycle_start = time.time()

        try:

            previous_state = {
                "files": dict(
                    state.get(
                        "files",
                        {}
                    )
                )
            }

            log(
                "STARTING COMPUTER SCAN..."
            )

            inventory, new_state = (
                scan_computer()
            )

            save_inventory(
                inventory
            )

            process_changes(
                previous_state,
                new_state,
            )

            state["files"] = new_state

            save_state(
                state
            )

            log(
                f"FILES DISCOVERED: "
                f"{len(inventory)}"
            )

            log(
                "SCAN COMPLETE"
            )

        except KeyboardInterrupt:

            log(
                "OCTOPUS AGENT STOPPED"
            )

            break

        except Exception as exc:

            log(
                f"AGENT ERROR: "
                f"{exc}"
            )

        elapsed = (
            time.time()
            - cycle_start
        )

        wait_seconds = max(
            1,
            POLL_SECONDS
            - int(elapsed),
        )

        time.sleep(
            wait_seconds
        )


if __name__ == "__main__":
    main()