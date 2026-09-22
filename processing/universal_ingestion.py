# ==========================================================
# PROJECT OCTOPUS — UNIVERSAL INGESTION ENGINE
# Pandas / NumPy free implementation
# ==========================================================

from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from uuid import uuid4
import re

from database.connection import SessionLocal

from database.models import (
    Source,
    Entity,
    EntityData,
    Event,
)


# ==========================================================
# CANONICAL FIELDS
# ==========================================================

CANONICAL_FIELDS = {
    "asset_id": [
        "asset_id",
        "assetid",
        "id",
        "device_id",
        "device_no",
        "device_number",
        "asset_no",
        "asset_number",
        "equipment_id",
    ],

    "asset_name": [
        "asset_name",
        "assetname",
        "name",
        "device_name",
        "device",
        "machine_name",
        "machine_desc",
        "description",
        "equipment_name",
    ],

    "location": [
        "location",
        "site",
        "site_loc",
        "site_location",
        "room",
        "zone",
        "area",
        "place",
        "building",
    ],

    "status": [
        "status",
        "condition",
        "state",
        "device_status",
        "asset_status",
        "operational_status",
    ],

    "last_updated": [
        "last_updated",
        "lastupdate",
        "updated",
        "updated_at",
        "modified",
        "modified_at",
        "timestamp",
        "last_seen",
        "datetime",
        "date_time",
    ],
}


REQUIRED_FIELDS = {
    "asset_id",
    "asset_name",
    "location",
    "status",
    "last_updated",
}


# ==========================================================
# BASIC HELPERS
# ==========================================================

def clean_header(value):

    value = str(
        value or ""
    ).strip()

    value = re.sub(
        r"[\s\-\/]+",
        "_",
        value,
    )

    value = re.sub(
        r"[^a-zA-Z0-9_]",
        "",
        value,
    )

    return value.lower()


def clean_text(value):

    if value is None:
        return ""

    return str(value).strip()


# ==========================================================
# STATUS NORMALIZATION
# ==========================================================

STATUS_MAP = {
    "active": "Active",
    "enabled": "Active",
    "online": "Active",
    "running": "Active",
    "working": "Active",
    "operational": "Active",
    "on": "Active",

    "inactive": "Inactive",
    "disabled": "Inactive",
    "offline": "Inactive",
    "stopped": "Inactive",
    "off": "Inactive",

    "maintenance": "Maintenance",
    "under maintenance": "Maintenance",
    "service": "Maintenance",

    "fault": "Fault",
    "faulty": "Fault",
    "error": "Fault",
    "failed": "Fault",
    "failure": "Fault",
}


def normalize_status(value):

    value = clean_text(
        value
    )

    if not value:
        return ""

    cleaned = value.lower()

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    return STATUS_MAP.get(
        cleaned,
        value.title(),
    )


# ==========================================================
# TIMESTAMP NORMALIZATION
# ==========================================================

def normalize_timestamp(value):

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value

    value = clean_text(
        value
    )

    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
    ]

    for fmt in formats:

        try:

            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )

        except ValueError:
            continue

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except ValueError:

        return None


# ==========================================================
# SCHEMA MAPPING
# ==========================================================

def similarity_score(
    source_field,
    canonical_field,
):

    source = clean_header(
        source_field
    )

    aliases = CANONICAL_FIELDS.get(
        canonical_field,
        [],
    )

    best = 0.0

    for alias in aliases:

        alias_clean = clean_header(
            alias
        )

        if source == alias_clean:

            best = max(
                best,
                0.95,
            )

        elif (
            source in alias_clean
            or alias_clean in source
        ):

            best = max(
                best,
                0.82,
            )

        else:

            ratio = SequenceMatcher(
                None,
                source,
                alias_clean,
            ).ratio()

            if ratio >= 0.85:

                best = max(
                    best,
                    0.80,
                )

            elif ratio >= 0.70:

                best = max(
                    best,
                    0.65,
                )

    return best


def value_pattern_score(
    values,
    canonical_field,
):

    samples = []

    for value in values:

        if value not in (
            None,
            "",
        ):

            samples.append(
                clean_text(value)
            )

    samples = samples[:10]

    if not samples:
        return 0.0

    if canonical_field == "asset_id":

        matches = 0

        for value in samples:

            if re.match(
                r"^[A-Za-z0-9_\-]+$",
                value,
            ):

                matches += 1

        return matches / len(
            samples
        )

    if canonical_field == "last_updated":

        matches = 0

        for value in samples:

            if normalize_timestamp(
                value
            ) is not None:

                matches += 1

        return matches / len(
            samples
        )

    if canonical_field == "status":

        known = {
            "online",
            "offline",
            "active",
            "inactive",
            "working",
            "running",
            "maintenance",
            "fault",
            "error",
            "stopped",
            "enabled",
            "disabled",
        }

        matches = 0

        for value in samples:

            if value.lower() in known:

                matches += 1

        return matches / len(
            samples
        )

    return 0.5


def detect_mapping(rows):

    if not rows:
        return []

    columns = list(
        rows[0].keys()
    )

    results = []

    used_canonical = set()

    for column in columns:

        values = []

        for row in rows[:10]:

            values.append(
                row.get(column)
            )

        best_field = None
        best_score = 0.0

        for canonical_field in CANONICAL_FIELDS:

            if canonical_field in used_canonical:
                continue

            name_score = similarity_score(
                column,
                canonical_field,
            )

            value_score = value_pattern_score(
                values,
                canonical_field,
            )

            semantic_score = (
                name_score * 0.7
                + value_score * 0.3
            )

            if semantic_score > best_score:

                best_score = semantic_score

                best_field = canonical_field

        if best_field is None:

            decision = "UNMAPPED"

        elif best_score >= 0.80:

            decision = "AUTO_MAP"

        elif best_score >= 0.60:

            decision = "REVIEW"

        else:

            decision = "UNMAPPED"

        if decision != "UNMAPPED":

            used_canonical.add(
                best_field
            )

        results.append(
            {
                "source_field": column,
                "source_column": column,
                "canonical_field": best_field,
                "target_field": best_field,
                "confidence": round(
                    best_score,
                    2,
                ),
                "decision": decision,
            }
        )

    return results


def build_mapping(
    mapping_results,
):

    mapping = {}

    for item in mapping_results:

        canonical = item.get(
            "canonical_field"
        )

        source = item.get(
            "source_field"
        )

        decision = item.get(
            "decision"
        )

        if (
            canonical
            and source
            and decision != "UNMAPPED"
        ):

            mapping[
                canonical
            ] = source

    return mapping


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_location(value):

    value = clean_text(
        value
    )

    if not value:
        return ""

    cleaned = value.lower()

    cleaned = re.sub(
        r"[._]+",
        " ",
        cleaned,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    gallery_match = re.fullmatch(
        r"gallery\s*(?:no\.?\s*)?(\d+)",
        cleaned,
    )

    if gallery_match:

        return (
            "Gallery "
            + gallery_match.group(1)
        )

    room_match = re.fullmatch(
        r"room\s*(?:no\.?\s*)?(\d+)",
        cleaned,
    )

    if room_match:

        return (
            "Room "
            + room_match.group(1)
        )

    zone_match = re.fullmatch(
        r"zone\s*(?:no\.?\s*)?(\d+)",
        cleaned,
    )

    if zone_match:

        return (
            "Zone "
            + zone_match.group(1)
        )

    area_match = re.fullmatch(
        r"area\s*(?:no\.?\s*)?(\d+)",
        cleaned,
    )

    if area_match:

        return (
            "Area "
            + area_match.group(1)
        )

    return value.title()


def normalize_asset_id(value):

    value = clean_text(
        value
    )

    if not value:
        return ""

    value = value.upper()

    value = re.sub(
        r"\s+",
        "",
        value,
    )

    return value.replace(
        "_",
        "-",
    )


def normalize_asset_name(value):

    value = clean_text(
        value
    )

    if not value:
        return ""

    return value


def normalize_record(
    row,
    mapping,
):

    return {
        "asset_id": normalize_asset_id(
            row.get(
                mapping.get(
                    "asset_id"
                )
            )
        ),

        "asset_name": normalize_asset_name(
            row.get(
                mapping.get(
                    "asset_name"
                )
            )
        ),

        "location": normalize_location(
            row.get(
                mapping.get(
                    "location"
                )
            )
        ),

        "status": normalize_status(
            row.get(
                mapping.get(
                    "status"
                )
            )
        ),

        "last_updated": normalize_timestamp(
            row.get(
                mapping.get(
                    "last_updated"
                )
            )
        ),
    }


# ==========================================================
# VALIDATION
# ==========================================================

def validate_record(
    record,
):

    errors = []

    if not record.get(
        "asset_id"
    ):

        errors.append(
            "Missing asset_id"
        )

    if not record.get(
        "asset_name"
    ):

        errors.append(
            "Missing asset_name"
        )

    if not record.get(
        "location"
    ):

        errors.append(
            "Missing location"
        )

    if not record.get(
        "status"
    ):

        errors.append(
            "Missing status"
        )

    if not record.get(
        "last_updated"
    ):

        errors.append(
            "Invalid or missing last_updated"
        )

    return errors


# ==========================================================
# STABLE ENTITY ID
# ==========================================================

def build_entity_id(
    source_id,
    source_record_id,
):

    raw = (
        f"{source_id}::{source_record_id}"
    )

    digest = sha256(
        raw.encode("utf-8")
    ).hexdigest()[:24]

    return (
        f"ENT-{digest}"
    )


# ==========================================================
# PAYLOAD CHECKSUM
# ==========================================================

def calculate_checksum(
    payload,
):

    raw = repr(
        sorted(
            (
                str(key),
                str(value),
            )
            for key, value
            in payload.items()
        )
    )

    return sha256(
        raw.encode("utf-8")
    ).hexdigest()


# ==========================================================
# UNIVERSAL INGESTION
# ==========================================================

def ingest_source(
    connector,
    source_type="Unknown",
    mapping_override=None,
):

    db = SessionLocal()

    try:

        # --------------------------------------------------
        # EXTRACT
        # --------------------------------------------------

        rows = connector.extract()

        if rows is None:

            rows = []

        rows = list(
            rows
        )

        row_count = len(
            rows
        )

        columns = (
            list(
                rows[0].keys()
            )
            if rows
            else []
        )

        extraction = {
            "row_count": row_count,
            "columns": columns,
        }

        # --------------------------------------------------
        # DETECT SOURCE SCHEMA
        # --------------------------------------------------

        mapping_results = detect_mapping(
            rows
        )

        detected_mapping = build_mapping(
            mapping_results
        )

        # --------------------------------------------------
        # FIRST PASS
        #
        # Detect the schema and wait for approval.
        # --------------------------------------------------

        if mapping_override is None:

            return {
                "success": False,
                "stage": "schema_mapping",
                "message": (
                    "Schema detected. "
                    "Administrator approval is required "
                    "before central ingestion."
                ),
                "extraction": extraction,
                "mapping_results": mapping_results,
                "detected_mapping": detected_mapping,
                "validation": {
                    "valid_rows": 0,
                    "invalid_rows": 0,
                    "errors": [],
                },
                "stored_entities": 0,
                "stored_data_records": 0,
            }

        # --------------------------------------------------
        # APPROVED MAPPING
        # --------------------------------------------------

        mapping = dict(
            mapping_override
        )

        missing_fields = (
            REQUIRED_FIELDS
            - set(
                mapping.keys()
            )
        )

        if missing_fields:

            return {
                "success": False,
                "stage": "schema_mapping",
                "message": (
                    "Approved schema mapping is incomplete."
                ),
                "missing_fields": sorted(
                    missing_fields
                ),
                "extraction": extraction,
                "mapping_results": mapping_results,
            }

        # --------------------------------------------------
        # SOURCE INFORMATION
        # --------------------------------------------------

        source_info = (
            connector.get_source_info()
        )

        source_id = source_info.get(
            "source_id"
        )

        source_name = source_info.get(
            "source_name"
            or source_info.get(
                "file_name"
            ),
            "Octopus Source",
        )

        connection_reference = (
            source_info.get(
                "connection_reference"
            )
        )

        if not source_id:

            source_key = (
                connection_reference
                or source_name
            )

            digest = sha256(
                str(
                    source_key
                ).encode(
                    "utf-8"
                )
            ).hexdigest()[:16]

            source_id = (
                f"SRC-{digest}"
            )

        # --------------------------------------------------
        # CURRENT TIME
        # --------------------------------------------------

        now = datetime.now(
            timezone.utc
        )

        # --------------------------------------------------
        # REGISTER / UPDATE SOURCE
        # --------------------------------------------------

        source = (
            db.query(Source)
            .filter(
                Source.source_id
                == source_id
            )
            .first()
        )

        if source is None:

            source = Source(
                source_id=source_id,
                source_name=source_name,
                source_type=source_type,
                connection_reference=(
                    connection_reference
                ),
                status="Active",
                last_sync_at=now,
            )

            db.add(
                source
            )

        else:

            source.source_name = (
                source_name
            )

            source.source_type = (
                source_type
            )

            source.connection_reference = (
                connection_reference
            )

            source.status = (
                "Active"
            )

            source.last_sync_at = (
                now
            )

        db.flush()

        # --------------------------------------------------
        # COUNTERS
        # --------------------------------------------------

        valid_count = 0

        invalid_count = 0

        validation_errors = []

        stored_entities = 0

        stored_data_records = 0

        created_entities = 0

        updated_entities = 0

        changed_entities = 0

        # --------------------------------------------------
        # PROCESS EACH SOURCE RECORD
        # --------------------------------------------------

        for index, original_row in enumerate(
            rows,
            start=1,
        ):

            normalized = normalize_record(
                original_row,
                mapping,
            )

            row_errors = validate_record(
                normalized
            )

            if row_errors:

                invalid_count += 1

                validation_errors.append(
                    {
                        "row": index,
                        "errors": row_errors,
                    }
                )

                continue

            valid_count += 1

            # ----------------------------------------------
            # STABLE SOURCE RECORD ID
            # ----------------------------------------------

            source_record_id = (
                normalized[
                    "asset_id"
                ]
                or f"ROW-{index}"
            )

            entity_id = (
                build_entity_id(
                    source_id,
                    source_record_id,
                )
            )

            # ----------------------------------------------
            # ORIGINAL SOURCE PAYLOAD
            # ----------------------------------------------

            original_payload = {}

            for key, value in (
                original_row.items()
            ):

                if isinstance(
                    value,
                    datetime,
                ):

                    original_payload[
                        str(key)
                    ] = (
                        value.isoformat()
                    )

                else:

                    original_payload[
                        str(key)
                    ] = value

            # ----------------------------------------------
            # CANONICAL PAYLOAD
            # ----------------------------------------------

            canonical_payload = {
                "asset_id": normalized[
                    "asset_id"
                ],

                "asset_name": normalized[
                    "asset_name"
                ],

                "location": normalized[
                    "location"
                ],

                "status": normalized[
                    "status"
                ],

                "last_updated": (
                    normalized[
                        "last_updated"
                    ].isoformat()
                    if normalized[
                        "last_updated"
                    ]
                    else None
                ),
            }

            complete_payload = {
                "canonical": canonical_payload,
                "original": original_payload,
                "source_record_id": (
                    source_record_id
                ),
            }

            checksum = calculate_checksum(
                complete_payload
            )

            # ----------------------------------------------
            # FIND EXISTING ENTITY
            # ----------------------------------------------

            entity = (
                db.query(Entity)
                .filter(
                    Entity.entity_id
                    == entity_id
                )
                .first()
            )

            is_new = (
                entity is None
            )

            previous_status = None

            previous_location = None

            if entity is None:

                entity = Entity(
                    entity_id=entity_id,
                    entity_type="asset",
                    entity_name=(
                        normalized[
                            "asset_name"
                        ]
                    ),
                    source_id=source_id,
                    location=(
                        normalized[
                            "location"
                        ]
                    ),
                    status=(
                        normalized[
                            "status"
                        ]
                    ),
                    attributes={
                        "source_record_id": (
                            source_record_id
                        ),
                        "canonical": (
                            canonical_payload
                        ),
                        "original": (
                            original_payload
                        ),
                    },
                    created_at=now,
                    updated_at=now,
                )

                db.add(
                    entity
                )

                created_entities += 1

            else:

                previous_status = (
                    entity.status
                )

                previous_location = (
                    entity.location
                )

                entity.entity_name = (
                    normalized[
                        "asset_name"
                    ]
                )

                entity.location = (
                    normalized[
                        "location"
                    ]
                )

                entity.status = (
                    normalized[
                        "status"
                    ]
                )

                entity.source_id = (
                    source_id
                )

                entity.attributes = {
                    "source_record_id": (
                        source_record_id
                    ),
                    "canonical": (
                        canonical_payload
                    ),
                    "original": (
                        original_payload
                    ),
                }

                entity.updated_at = (
                    now
                )

                updated_entities += 1

                if (
                    previous_status
                    != normalized[
                        "status"
                    ]
                    or previous_location
                    != normalized[
                        "location"
                    ]
                ):

                    changed_entities += 1

            db.flush()

            stored_entities += 1

            # ----------------------------------------------
            # ENTITY DATA SNAPSHOT
            # ----------------------------------------------

            latest_data = (
                db.query(
                    EntityData
                )
                .filter(
                    EntityData.entity_id
                    == entity_id,
                    EntityData.source_id
                    == source_id,
                )
                .order_by(
                    EntityData.received_at.desc()
                )
                .first()
            )

            should_store_snapshot = (
                latest_data is None
                or latest_data.checksum
                != checksum
            )

            if should_store_snapshot:

                entity_data = EntityData(
                    entity_id=entity_id,
                    source_id=source_id,
                    schema_version="1.0",
                    payload=complete_payload,
                    checksum=checksum,
                    observed_at=(
                        normalized[
                            "last_updated"
                        ]
                        or now
                    ),
                    received_at=now,
                )

                db.add(
                    entity_data
                )

                stored_data_records += 1

            # ----------------------------------------------
            # EVENT: NEW ENTITY
            # ----------------------------------------------

            if is_new:

                event = Event(
                    event_id=(
                        "EVT-"
                        + uuid4().hex
                    ),
                    entity_id=entity_id,
                    source_id=source_id,
                    event_type="entity_created",
                    actor_id="OCTOPUS_AGENT",
                    actor_type="system",
                    location=(
                        normalized[
                            "location"
                        ]
                    ),
                    occurred_at=now,
                    event_metadata={
                        "source_record_id": (
                            source_record_id
                        ),
                        "source_type": (
                            source_type
                        ),
                    },
                )

                db.add(
                    event
                )

            # ----------------------------------------------
            # EVENT: STATUS CHANGE
            # ----------------------------------------------

            else:

                if (
                    previous_status
                    != normalized[
                        "status"
                    ]
                ):

                    event = Event(
                        event_id=(
                            "EVT-"
                            + uuid4().hex
                        ),
                        entity_id=entity_id,
                        source_id=source_id,
                        event_type="status_changed",
                        actor_id="OCTOPUS_AGENT",
                        actor_type="system",
                        location=(
                            normalized[
                                "location"
                            ]
                        ),
                        occurred_at=now,
                        event_metadata={
                            "old_status": (
                                previous_status
                            ),
                            "new_status": (
                                normalized[
                                    "status"
                                ]
                            ),
                        },
                    )

                    db.add(
                        event
                    )

                # ------------------------------------------
                # EVENT: LOCATION CHANGE
                # ------------------------------------------

                if (
                    previous_location
                    != normalized[
                        "location"
                    ]
                ):

                    event = Event(
                        event_id=(
                            "EVT-"
                            + uuid4().hex
                        ),
                        entity_id=entity_id,
                        source_id=source_id,
                        event_type="location_changed",
                        actor_id="OCTOPUS_AGENT",
                        actor_type="system",
                        location=(
                            normalized[
                                "location"
                            ]
                        ),
                        occurred_at=now,
                        event_metadata={
                            "old_location": (
                                previous_location
                            ),
                            "new_location": (
                                normalized[
                                    "location"
                                ]
                            ),
                        },
                    )

                    db.add(
                        event
                    )

        # --------------------------------------------------
        # COMMIT ALL CHANGES
        # --------------------------------------------------

        db.commit()

        return {
            "success": True,
            "stage": "completed",
            "message": (
                "Source successfully processed and "
                "synchronized with central PostgreSQL."
            ),

            "source": {
                "source_id": source_id,
                "source_name": source_name,
                "source_type": source_type,
            },

            "extraction": extraction,

            "mapping": mapping,

            "mapping_results": mapping_results,

            "validation": {
                "valid_rows": valid_count,
                "invalid_rows": invalid_count,
                "errors": validation_errors,
            },

            "stored_entities": (
                stored_entities
            ),

            "stored_data_records": (
                stored_data_records
            ),

            "created_entities": (
                created_entities
            ),

            "updated_entities": (
                updated_entities
            ),

            "changed_entities": (
                changed_entities
            ),

            "synchronization": {
                "mode": (
                    "authorized-source-polling"
                ),
                "timestamp": (
                    now.isoformat()
                ),
            },
        }

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()