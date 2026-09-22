# ==================================================
# PROJECT OCTOPUS — UNIVERSAL DATABASE REPOSITORY
# ==================================================

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Source,
    Entity,
    EntityData,
    Event,
    Location,
    SyncRun,
    Conflict,
    AuditLog
)


# ==================================================
# SOURCE OPERATIONS
# ==================================================

def create_source(
    db: Session,
    source_data: dict
):
    source = Source(
        source_id=source_data["source_id"],
        source_name=source_data["source_name"],
        source_type=source_data["source_type"],
        connection_reference=source_data.get(
            "connection_reference"
        ),
        status=source_data.get(
            "status",
            "active"
        )
    )

    db.add(source)
    db.commit()
    db.refresh(source)

    return source


def get_source(
    db: Session,
    source_id: str
):
    statement = select(Source).where(
        Source.source_id == source_id
    )

    return db.scalar(statement)


# ==================================================
# ENTITY OPERATIONS
# ==================================================

def create_entity(
    db: Session,
    entity_data: dict
):
    entity = Entity(
        entity_id=entity_data["entity_id"],
        entity_type=entity_data["entity_type"],
        entity_name=entity_data.get("entity_name"),
        source_id=entity_data.get("source_id"),
        location=entity_data.get("location"),
        status=entity_data.get("status"),
        attributes=entity_data.get(
            "attributes",
            {}
        )
    )

    db.add(entity)
    db.commit()
    db.refresh(entity)

    return entity


def get_entity(
    db: Session,
    entity_id: str
):
    statement = select(Entity).where(
        Entity.entity_id == entity_id
    )

    return db.scalar(statement)


def get_all_entities(
    db: Session
):
    statement = select(Entity)

    return list(
        db.scalars(statement).all()
    )


def upsert_entity(
    db: Session,
    entity_data: dict
):
    existing = get_entity(
        db,
        entity_data["entity_id"]
    )

    if existing is None:
        return create_entity(
            db,
            entity_data
        )

    if "entity_type" in entity_data:
        existing.entity_type = (
            entity_data["entity_type"]
        )

    if "entity_name" in entity_data:
        existing.entity_name = (
            entity_data["entity_name"]
        )

    if "source_id" in entity_data:
        existing.source_id = (
            entity_data["source_id"]
        )

    if "location" in entity_data:
        existing.location = (
            entity_data["location"]
        )

    if "status" in entity_data:
        existing.status = (
            entity_data["status"]
        )

    if "attributes" in entity_data:
        existing.attributes = (
            entity_data["attributes"]
        )

    existing.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(existing)

    return existing


# ==================================================
# ENTITY DATA OPERATIONS
# ==================================================

def create_entity_data(
    db: Session,
    data
):
    record = EntityData(
        entity_id=data["entity_id"],
        source_id=data.get("source_id"),
        schema_version=data.get(
            "schema_version"
        ),
        payload=data.get(
            "payload",
            {}
        ),
        checksum=data.get(
            "checksum"
        ),
        observed_at=data.get(
            "observed_at"
        )
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def get_entity_data(
    db: Session,
    entity_id: str
):
    statement = select(EntityData).where(
        EntityData.entity_id == entity_id
    )

    return list(
        db.scalars(statement).all()
    )


# ==================================================
# EVENT OPERATIONS
# ==================================================

def create_event(
    db: Session,
    event_data: dict
):
    event = Event(
        event_id=event_data["event_id"],
        entity_id=event_data.get(
            "entity_id"
        ),
        event_type=event_data["event_type"],
        actor_id=event_data.get(
            "actor_id"
        ),
        actor_type=event_data.get(
            "actor_type"
        ),
        location=event_data.get(
            "location"
        ),
        source_id=event_data.get(
            "source_id"
        ),
        occurred_at=event_data.get(
            "occurred_at",
            datetime.utcnow()
        ),
        event_metadata=event_data.get(
            "event_metadata",
            {}
        )
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


def get_entity_events(
    db: Session,
    entity_id: str
):
    statement = (
        select(Event)
        .where(
            Event.entity_id == entity_id
        )
        .order_by(
            Event.occurred_at.desc()
        )
    )

    return list(
        db.scalars(statement).all()
    )


# ==================================================
# LOCATION OPERATIONS
# ==================================================

def create_location(
    db: Session,
    location_data: dict
):
    location = Location(
        location_id=location_data["location_id"],
        location_name=location_data["location_name"],
        parent_location_id=location_data.get(
            "parent_location_id"
        ),
        location_metadata=location_data.get(
            "location_metadata",
            {}
        )
    )

    db.add(location)
    db.commit()
    db.refresh(location)

    return location


def get_location(
    db: Session,
    location_id: str
):
    statement = select(Location).where(
        Location.location_id == location_id
    )

    return db.scalar(statement)


# ==================================================
# SYNCHRONIZATION OPERATIONS
# ==================================================

def create_sync_run(
    db: Session,
    sync_data: dict
):
    sync_run = SyncRun(
        sync_id=sync_data["sync_id"],
        source_id=sync_data["source_id"],
        started_at=sync_data.get(
            "started_at",
            datetime.utcnow()
        ),
        status=sync_data.get(
            "status",
            "running"
        ),
        records_received=sync_data.get(
            "records_received",
            0
        ),
        records_processed=sync_data.get(
            "records_processed",
            0
        ),
        records_failed=sync_data.get(
            "records_failed",
            0
        )
    )

    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    return sync_run


def update_sync_run(
    db: Session,
    sync_id: str,
    updates: dict
):
    statement = select(SyncRun).where(
        SyncRun.sync_id == sync_id
    )

    sync_run = db.scalar(statement)

    if sync_run is None:
        return None

    for field, value in updates.items():

        if hasattr(sync_run, field):
            setattr(
                sync_run,
                field,
                value
            )

    db.commit()
    db.refresh(sync_run)

    return sync_run


# ==================================================
# CONFLICT OPERATIONS
# ==================================================

def create_conflict(
    db: Session,
    conflict_data: dict
):
    conflict = Conflict(
        conflict_id=conflict_data["conflict_id"],
        entity_id=conflict_data["entity_id"],
        field_name=conflict_data["field_name"],
        source_a=conflict_data.get(
            "source_a"
        ),
        value_a=conflict_data.get(
            "value_a"
        ),
        source_b=conflict_data.get(
            "source_b"
        ),
        value_b=conflict_data.get(
            "value_b"
        ),
        resolution=conflict_data.get(
            "resolution"
        ),
        selected_value=conflict_data.get(
            "selected_value"
        )
    )

    db.add(conflict)
    db.commit()
    db.refresh(conflict)

    return conflict


# ==================================================
# AUDIT OPERATIONS
# ==================================================

def create_audit_log(
    db: Session,
    audit_data: dict
):
    log = AuditLog(
        audit_id=audit_data["audit_id"],
        actor_id=audit_data.get(
            "actor_id"
        ),
        action=audit_data["action"],
        entity_id=audit_data.get(
            "entity_id"
        ),
        source_id=audit_data.get(
            "source_id"
        ),
        timestamp=audit_data.get(
            "timestamp",
            datetime.utcnow()
        ),
        details=audit_data.get(
            "details",
            {}
        )
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return log