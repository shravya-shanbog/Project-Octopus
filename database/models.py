# ==================================================
# PROJECT OCTOPUS — UNIVERSAL DATA MODEL
# ==================================================

from datetime import datetime

from sqlalchemy import (
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    JSON
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from database.connection import Base


# --------------------------------------------------
# POSTGRESQL JSONB + SQLITE DEVELOPMENT SUPPORT
# --------------------------------------------------

try:
    from sqlalchemy.dialects.postgresql import JSONB

    JSON_DATA_TYPE = JSON().with_variant(
        JSONB(),
        "postgresql"
    )

except ImportError:
    JSON_DATA_TYPE = JSON


# ==================================================
# 1. SOURCES
# ==================================================

class Source(Base):

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    source_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True
    )

    source_name: Mapped[str] = mapped_column(
        String(255)
    )

    source_type: Mapped[str] = mapped_column(
        String(100)
    )

    connection_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="active"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )


# ==================================================
# 2. UNIVERSAL ENTITIES
# ==================================================

class Entity(Base):

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    entity_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        index=True
    )

    entity_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    source_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("sources.source_id"),
        nullable=True,
        index=True
    )

    location: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    attributes: Mapped[dict | None] = mapped_column(
        JSON_DATA_TYPE,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


# ==================================================
# 3. ENTITY DATA
# ==================================================

class EntityData(Base):

    __tablename__ = "entity_data"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    entity_id: Mapped[str] = mapped_column(
        String(150),
        ForeignKey("entities.entity_id"),
        index=True
    )

    source_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("sources.source_id"),
        nullable=True,
        index=True
    )

    schema_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    payload: Mapped[dict] = mapped_column(
        JSON_DATA_TYPE
    )

    checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True
    )

    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


# ==================================================
# 4. EVENTS / INTERACTIONS
# ==================================================

class Event(Base):

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    event_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    entity_id: Mapped[str | None] = mapped_column(
        String(150),
        ForeignKey("entities.entity_id"),
        nullable=True,
        index=True
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        index=True
    )

    actor_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True
    )

    actor_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    location: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    source_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("sources.source_id"),
        nullable=True,
        index=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    event_metadata: Mapped[dict | None] = mapped_column(
        JSON_DATA_TYPE,
        nullable=True
    )


# ==================================================
# 5. LOCATIONS
# ==================================================

class Location(Base):

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    location_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    location_name: Mapped[str] = mapped_column(
        String(500)
    )

    parent_location_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    location_metadata: Mapped[dict | None] = mapped_column(
        JSON_DATA_TYPE,
        nullable=True
    )


# ==================================================
# 6. SYNCHRONIZATION RUNS
# ==================================================

class SyncRun(Base):

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    sync_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    source_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("sources.source_id"),
        index=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="running"
    )

    records_received: Mapped[int] = mapped_column(
        default=0
    )

    records_processed: Mapped[int] = mapped_column(
        default=0
    )

    records_failed: Mapped[int] = mapped_column(
        default=0
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )


# ==================================================
# 7. CONFLICTS
# ==================================================

class Conflict(Base):

    __tablename__ = "conflicts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    conflict_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    entity_id: Mapped[str] = mapped_column(
        String(150),
        ForeignKey("entities.entity_id"),
        index=True
    )

    field_name: Mapped[str] = mapped_column(
        String(150)
    )

    source_a: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    value_a: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    source_b: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    value_b: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    resolution: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    selected_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


# ==================================================
# 8. AUDIT LOGS
# ==================================================

class AuditLog(Base):

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    audit_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    actor_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    action: Mapped[str] = mapped_column(
        String(100)
    )

    entity_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    source_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    details: Mapped[dict | None] = mapped_column(
        JSON_DATA_TYPE,
        nullable=True
    )