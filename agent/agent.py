from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ============================================================
# PROJECT OCTOPUS — REAL-TIME COMPUTER DISCOVERY AGENT
# ============================================================
# Design:
#   • One initial full inventory scan of C:\ and D:\ (when present)
#   • Windows file-system events watch the drives continuously
#   • New/changed CSV/XLS/XLSX files are automatically sent to
#     the SAME /api/sync/file pipeline used by the website
#   • Existing files are baselined and are NOT bulk-ingested
#   • Octopus data/import files are excluded to prevent loops
#   • A lightweight inventory refresh runs every 3 minutes
#
# Automatic path:
# Computer -> Watcher -> /api/sync/file ->
# Extract -> Schema Mapping -> Normalize -> Validate ->
# Identity -> Conflict Handling -> PostgreSQL ->
# Search / Dashboard / Monitoring
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INVENTORY_FILE = DATA_DIR / "computer_inventory.json"
STATE_FILE = DATA_DIR / "agent_state.json"

STATE_VERSION = 5
BACKEND_URL = os.getenv("OCTOPUS_BACKEND_URL", "http://127.0.0.1:8000")

# Event-driven monitoring is immediate.
# This value controls the periodic full inventory refresh and is also
# reported as the inventory interval.
INVENTORY_REFRESH_SECONDS = 180  # full inventory refresh every 3 minutes
POLL_SECONDS = 3  # check known structured files every 3 seconds

REQUEST_TIMEOUT = 180
STABLE_CHECK_DELAY = 1.0
MAX_INGEST_SIZE_BYTES = 250 * 1024 * 1024
SUPPORTED_DATA_EXTENSIONS = {".csv", ".xls", ".xlsx"}

SCAN_DRIVES = [Path("C:/"), Path("D:/")]

PROJECT_IMPORTS_DIR = (BASE_DIR / "data" / "imports").resolve()
PROJECT_DATA_DIR = DATA_DIR.resolve()

SKIP_DIRECTORY_NAMES = {
    "$recycle.bin",
    "system volume information",
}

# These are very large / system-heavy locations. They remain in the
# inventory only when already represented by a file event; we do not
# need them for structured-data ingestion.
WATCH_SKIP_PARTS = {
    "$recycle.bin",
    "system volume information",
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Project-Octopus-Agent/6.0"
})

print_lock = threading.Lock()
state_lock = threading.Lock()


# ============================================================
# LOGGING / TIME
# ============================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    with print_lock:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] {message}", flush=True)


# ============================================================
# JSON STATE
# ============================================================

def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8"
    )
    temp.replace(path)


# ============================================================
# PATH / FILE HELPERS
# ============================================================

def normalize_path(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except Exception:
        return str(path.absolute()).lower()


def is_inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except (ValueError, OSError):
        return False


def should_ignore_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path

    if is_inside(resolved, PROJECT_IMPORTS_DIR):
        return True

    # Ignore generated runtime data under the project data directory
    # for event-driven ingestion. The inventory endpoint reads the
    # generated inventory JSON separately.
    if is_inside(resolved, PROJECT_DATA_DIR):
        return True

    lowered_parts = {
        part.lower()
        for part in str(resolved).replace("/", "\\").split("\\")
        if part
    }

    if lowered_parts & WATCH_SKIP_PARTS:
        return True

    return False


def safe_stat(path: Path):
    try:
        return path.stat()
    except (OSError, PermissionError):
        return None


def file_fingerprint(path: Path) -> str | None:
    stat_result = safe_stat(path)
    if stat_result is None:
        return None

    raw = "|".join([
        normalize_path(path),
        str(stat_result.st_size),
        str(stat_result.st_mtime_ns),
    ])

    return hashlib.sha256(
        raw.encode("utf-8", errors="ignore")
    ).hexdigest()


def source_key_for(path: Path) -> str:
    return "computer-file:" + hashlib.sha256(
        normalize_path(path).encode("utf-8", errors="ignore")
    ).hexdigest()[:32]


def connector_type_for(path: Path) -> str:
    if path.suffix.lower() == ".csv":
        return "csv"
    return "excel"


def wait_until_stable(path: Path) -> bool:
    first = safe_stat(path)
    if first is None:
        return False

    time.sleep(STABLE_CHECK_DELAY)

    second = safe_stat(path)
    if second is None:
        return False

    return (
        first.st_size == second.st_size
        and first.st_mtime_ns == second.st_mtime_ns
    )


# ============================================================
# COMPUTER INVENTORY
# ============================================================

def build_inventory_record(path: Path, stat_result) -> dict[str, Any]:
    extension = path.suffix.lower()
    drive = path.drive or (
        path.parts[0] if path.parts else ""
    )

    return {
        "name": path.name,
        "path": str(path),
        "extension": extension,
        "type": extension.lstrip(".") if extension else "file",
        "drive": drive,
        "size_bytes": int(stat_result.st_size),
        "modified_at": datetime.fromtimestamp(
            stat_result.st_mtime,
            tz=timezone.utc
        ).isoformat(),
        "modified_epoch": stat_result.st_mtime,
        "data_source": (
            extension in SUPPORTED_DATA_EXTENSIONS
        ),
    }


def scan_computer() -> tuple[list[dict[str, Any]], dict[str, int]]:
    records: list[dict[str, Any]] = []

    counts = {
        "files": 0,
        "permission_skips": 0,
        "walk_errors": 0,
    }

    available_drives = [
        drive for drive in SCAN_DRIVES
        if drive.exists()
    ]

    for drive in available_drives:

        log(f"SCANNING DRIVE: {drive}")

        def onerror(_error):
            counts["walk_errors"] += 1

        for root, dirs, files in os.walk(
            str(drive),
            topdown=True,
            onerror=onerror
        ):

            root_path = Path(root)

            kept_dirs = []

            for dirname in dirs:
                candidate = root_path / dirname

                if should_ignore_path(candidate):
                    continue

                kept_dirs.append(dirname)

            dirs[:] = kept_dirs

            for filename in files:
                path = root_path / filename

                if should_ignore_path(path):
                    continue

                # Excel temporary lock files
                if filename.startswith("~$"):
                    continue

                if filename.lower().endswith(".tmp"):
                    continue

                stat_result = safe_stat(path)

                if stat_result is None:
                    counts["permission_skips"] += 1
                    continue

                records.append(
                    build_inventory_record(
                        path,
                        stat_result
                    )
                )

                counts["files"] += 1

    records.sort(
        key=lambda item:
        str(item.get("path", "")).lower()
    )

    return records, counts


def update_inventory(
    records: list[dict[str, Any]],
    scan_counts: dict[str, int]
) -> None:

    available_drives = [
        str(drive)
        for drive in SCAN_DRIVES
        if drive.exists()
    ]

    payload = {
        "success": True,
        "computer_name": socket.gethostname(),
        "generated_at": now_iso(),
        "agent_version": "6.0",
        "inventory_refresh_seconds":
            INVENTORY_REFRESH_SECONDS,
        "file_event_monitoring": True,
        "drives": available_drives,
        "total_files": len(records),
        "scan": scan_counts,
        "files": records,
    }

    save_json(
        INVENTORY_FILE,
        payload
    )


# ============================================================
# STATE
# ============================================================

def state_fingerprints(state: dict[str, Any]) -> dict[str, str]:
    fingerprints = state.get("fingerprints")

    if not isinstance(fingerprints, dict):
        fingerprints = {}
        state["fingerprints"] = fingerprints

    return fingerprints


def is_known_fingerprint(
    path: Path,
    state: dict[str, Any]
) -> bool:

    key = normalize_path(path)
    current = file_fingerprint(path)

    if current is None:
        return False

    return state_fingerprints(state).get(key) == current


def remember_fingerprint(
    path: Path,
    state: dict[str, Any],
    result: str
) -> None:

    key = normalize_path(path)
    current = file_fingerprint(path)

    if current is None:
        return

    state_fingerprints(state)[key] = current

    results = state.setdefault(
        "last_results",
        {}
    )

    results[key] = {
        "result": result,
        "name": path.name,
        "updated_at": now_iso(),
    }


# ============================================================
# BACKEND
# ============================================================

def backend_is_ready() -> bool:
    try:
        response = session.get(
            f"{BACKEND_URL}/health",
            timeout=5
        )
        return response.ok
    except requests.RequestException:
        return False


def ingest_file(
    path: Path,
    state: dict[str, Any]
) -> tuple[bool, str]:

    extension = path.suffix.lower()

    if extension not in SUPPORTED_DATA_EXTENSIONS:
        remember_fingerprint(
            path,
            state,
            "inventory-only"
        )
        return True, "inventory-only"

    if should_ignore_path(path):
        return True, "ignored"

    stat_result = safe_stat(path)

    if stat_result is None:
        return False, "file-not-accessible"

    if stat_result.st_size > MAX_INGEST_SIZE_BYTES:
        return False, "file-too-large"

    if not wait_until_stable(path):
        return False, "file-still-changing"

    # The file may disappear while it is being written/moved.
    if not path.exists():
        return False, "file-disappeared"

    log(
        f"INGESTING DATA SOURCE: {path}"
    )

    try:
        with path.open("rb") as file_handle:

            response = session.post(
                f"{BACKEND_URL}/api/sync/file",
                files={
                    "file": (
                        path.name,
                        file_handle,
                        "application/octet-stream"
                    )
                },
                data={
                    "source_key":
                        source_key_for(path),

                    "connector_type":
                        connector_type_for(path),

                    "mapping_json":
                        "{}",
                },
                timeout=REQUEST_TIMEOUT,
            )

        if response.ok:

            try:
                result = response.json()

                rows = result.get(
                    "rows_processed",
                    result.get(
                        "processed_rows",
                        "?"
                    )
                )

                valid = result.get(
                    "valid_rows",
                    "?"
                )

                inserted = result.get(
                    "inserted",
                    "?"
                )

                updated = result.get(
                    "updated",
                    "?"
                )

                log(
                    f"INGESTION SUCCESS: {path.name} | "
                    f"rows={rows} | "
                    f"valid={valid} | "
                    f"inserted={inserted} | "
                    f"updated={updated}"
                )

            except Exception:
                log(
                    f"INGESTION SUCCESS: {path.name}"
                )

            remember_fingerprint(
                path,
                state,
                "ingested"
            )

            return True, "ingested"

        try:
            detail = response.json().get(
                "detail",
                response.text[:500]
            )
        except Exception:
            detail = response.text[:500]

        log(
            f"INGESTION FAILED: {path.name} | "
            f"HTTP {response.status_code} | "
            f"{detail}"
        )

        return False, f"http-{response.status_code}"

    except requests.RequestException as exc:

        log(
            f"BACKEND REQUEST FAILED: "
            f"{path.name} | {exc}"
        )

        return False, "backend-unreachable"

    except Exception as exc:

        log(
            f"INGESTION FAILED: "
            f"{path.name} | {exc}"
        )

        return False, "exception"


# ============================================================
# FILE EVENT HANDLER
# ============================================================

class OctopusFileHandler(FileSystemEventHandler):

    def __init__(self, state: dict[str, Any]):
        super().__init__()
        self.state = state

    def handle_candidate(
        self,
        path_string: str
    ) -> None:

        path = Path(path_string)

        if should_ignore_path(path):
            return

        if not path.exists():
            return

        extension = path.suffix.lower()

        if extension not in SUPPORTED_DATA_EXTENSIONS:
            return

        # Do not ingest an event for an unchanged file.
        if is_known_fingerprint(
            path,
            self.state
        ):
            return

        log(
            f"NEW / CHANGED DATA SOURCE: {path}"
        )

        success, result = ingest_file(
            path,
            self.state
        )

        if not success:
            # For transient errors, the next filesystem event or the
            # periodic inventory cycle can provide another opportunity.
            if result == "backend-unreachable":
                return

            if result == "file-still-changing":
                return

    def on_created(self, event):

        if event.is_directory:
            return

        self.handle_candidate(
            event.src_path
        )

    def on_modified(self, event):

        if event.is_directory:
            return

        self.handle_candidate(
            event.src_path
        )

    def on_moved(self, event):

        if event.is_directory:
            return

        self.handle_candidate(
            event.dest_path
        )


# ============================================================
# INITIAL BASELINE
# ============================================================

def create_initial_baseline(
    records: list[dict[str, Any]],
    state: dict[str, Any]
) -> None:

    for record in records:

        path = Path(
            str(record["path"])
        )

        current = file_fingerprint(path)

        if current is not None:
            state_fingerprints(
                state
            )[normalize_path(path)] = current

    state["initialized"] = True
    state["baseline_created_at"] = now_iso()
    state["last_scan_at"] = now_iso()
    state["last_scan_files"] = len(records)
    state["last_changed_sources"] = 0

    save_json(
        STATE_FILE,
        state
    )


# ============================================================
# 3-SECOND CHANGE CHECK
# ============================================================

def three_second_poll_loop(
    state: dict[str, Any],
    stop_event: threading.Event
) -> None:
    """
    Every 3 seconds, check all currently known structured files.
    New files are still handled by Watchdog immediately.
    This poll catches modifications that may not surface reliably
    through a file event.
    """

    while not stop_event.wait(POLL_SECONDS):

        try:
            inventory = load_json(
                INVENTORY_FILE,
                {}
            )

            for item in inventory.get("files", []):
                extension = str(
                    item.get("extension", "")
                ).lower()

                if extension not in SUPPORTED_DATA_EXTENSIONS:
                    continue

                path = Path(
                    str(item.get("path", ""))
                )

                if not path.exists():
                    continue

                if should_ignore_path(path):
                    continue

                if is_known_fingerprint(
                    path,
                    state
                ):
                    continue

                log(
                    f"3-SECOND CHECK DETECTED CHANGE: "
                    f"{path}"
                )

                ingest_file(
                    path,
                    state
                )

            save_json(
                STATE_FILE,
                state
            )

        except Exception as exc:

            log(
                f"3-SECOND CHECK ERROR: {exc}"
            )


# ============================================================
# PERIODIC INVENTORY REFRESH
# ============================================================

def inventory_refresh_loop(
    state: dict[str, Any],
    stop_event: threading.Event
) -> None:

    while not stop_event.wait(
        INVENTORY_REFRESH_SECONDS
    ):

        try:

            records, scan_counts = scan_computer()

            update_inventory(
                records,
                scan_counts
            )

            state["last_scan_at"] = now_iso()
            state["last_scan_files"] = len(
                records
            )

            save_json(
                STATE_FILE,
                state
            )

            log(
                f"PERIODIC INVENTORY UPDATED: "
                f"{len(records)} FILES"
            )

        except Exception as exc:

            log(
                f"INVENTORY REFRESH FAILED: {exc}"
            )


# ============================================================
# MAIN
# ============================================================

def run() -> None:

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    state = load_json(
        STATE_FILE,
        {}
    )

    if not isinstance(state, dict):
        state = {}

    if state.get("state_version") != STATE_VERSION:
        state = {
            "state_version": STATE_VERSION,
            "initialized": False,
            "fingerprints": {},
            "last_results": {},
        }

    state.setdefault(
        "state_version",
        STATE_VERSION
    )

    state.setdefault(
        "initialized",
        False
    )

    state.setdefault(
        "fingerprints",
        {}
    )

    state.setdefault(
        "last_results",
        {}
    )

    print("=" * 78)
    print("PROJECT OCTOPUS")
    print("REAL-TIME COMPUTER DISCOVERY AGENT")
    print("=" * 78)

    log(
        f"BACKEND: {BACKEND_URL}"
    )

    log(
        "DRIVES: C:\\, D:\\ (when present)"
    )

    log(
        "FILE EVENTS: REAL-TIME"
    )

    log(
        "CHANGE CHECK: EVERY 3 SECONDS"
    )

    log(
        "FULL COMPUTER INVENTORY REFRESH: EVERY 3 MINUTES"
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
        "NEW / MODIFIED STRUCTURED FILES: "
        "AUTOMATIC"
    )

    log(
        "PROJECT IMPORT LOOP: BLOCKED"
    )

    log(
        "OTHER FILE TYPES: INVENTORY ONLY"
    )

    print("=" * 78)

    if backend_is_ready():
        log("BACKEND READY")
    else:
        log(
            "WARNING: BACKEND IS NOT READY. "
            "Start backend before ingestion."
        )

    # --------------------------------------------------------
    # One initial full scan = inventory + baseline.
    # Existing files are NOT ingested.
    # --------------------------------------------------------

    log("STARTING INITIAL COMPUTER INVENTORY...")

    records, scan_counts = scan_computer()

    update_inventory(
        records,
        scan_counts
    )

    log(
        f"COMPUTER INVENTORY UPDATED: "
        f"{len(records)} FILES"
    )

    if not state.get("initialized", False):

        log(
            "INITIAL BASELINE CREATED + "
            "STRUCTURED DATA INGESTION STARTING..."
        )

        # Every existing CSV/XLS/XLSX discovered on C:/D: is sent through
        # the same /api/sync/file endpoint used by the website. The backend
        # performs Extract -> Schema Detection -> Mapping -> Normalize ->
        # Validate -> Identity -> Conflict -> PostgreSQL.
        structured = [
            Path(str(r["path"]))
            for r in records
            if str(r.get("extension", "")).lower()
            in SUPPORTED_DATA_EXTENSIONS
        ]

        log(
            f"INITIAL STRUCTURED SOURCES FOUND: "
            f"{len(structured)}"
        )

        for path in structured:
            if not path.exists():
                continue

            try:
                success, result = ingest_file(
                    path,
                    state
                )

                if not success:
                    log(
                        f"INITIAL INGESTION RETRY LATER: "
                        f"{path.name} | {result}"
                    )

            except Exception as exc:
                log(
                    f"INITIAL INGESTION ERROR: "
                    f"{path.name} | {exc}"
                )

        state["initialized"] = True
        state["initial_ingestion_completed_at"] = now_iso()
        state["last_scan_at"] = now_iso()
        state["last_scan_files"] = len(records)

        save_json(
            STATE_FILE,
            state
        )

        log(
            "INITIAL STRUCTURED DATA INGESTION COMPLETE."
        )

    else:

        log(
            "EXISTING AGENT STATE FOUND: "
            "3-SECOND POLL + FILE EVENT MONITORING ACTIVE."
        )

    # --------------------------------------------------------
    # Watch all available drives.
    # --------------------------------------------------------

    observer = Observer()
    handler = OctopusFileHandler(state)

    watched = 0

    for drive in SCAN_DRIVES:

        if not drive.exists():
            continue

        try:

            observer.schedule(
                handler,
                str(drive),
                recursive=True
            )

            watched += 1

            log(
                f"FILE EVENT WATCH ENABLED: {drive}"
            )

        except Exception as exc:

            log(
                f"FILE EVENT WATCH FAILED: "
                f"{drive} | {exc}"
            )

    observer.start()

    # --------------------------------------------------------
    # Periodic full inventory refresh runs in parallel.
    # The event watcher handles immediate file changes.
    # --------------------------------------------------------

    stop_event = threading.Event()

    refresh_thread = threading.Thread(
        target=inventory_refresh_loop,
        args=(state, stop_event),
        daemon=True
    )

    refresh_thread.start()

    poll_thread = threading.Thread(
        target=three_second_poll_loop,
        args=(state, stop_event),
        daemon=True
    )

    poll_thread.start()

    log(
        f"MONITORING ACTIVE: "
        f"{watched} DRIVE(S)"
    )

    log(
        f"3-SECOND CHANGE CHECK ACTIVE"
    )

    log(
        "NEW OR MODIFIED CSV/XLS/XLSX FILES "
        "WILL BE SENT TO THE OCTOPUS PIPELINE "
        "AUTOMATICALLY."
    )

    try:

        while True:
            time.sleep(1)

    except KeyboardInterrupt:

        log(
            "STOPPING OCTOPUS AGENT..."
        )

        stop_event.set()

        observer.stop()
        observer.join(
            timeout=10
        )

        save_json(
            STATE_FILE,
            state
        )

        log(
            "Octopus Agent stopped."
        )


if __name__ == "__main__":
    run()

