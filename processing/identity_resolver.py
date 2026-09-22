# ==================================================
# PROJECT OCTOPUS — IDENTITY RESOLUTION ENGINE
# ==================================================

import hashlib
import re


# --------------------------------------------------
# TEXT CLEANING
# --------------------------------------------------

def clean_identifier(value):
    """
    Clean an identifier without changing its meaning.
    """

    if value is None:
        return None

    value = str(value).strip().upper()

    value = re.sub(
        r"\s+",
        "",
        value
    )

    return value


# --------------------------------------------------
# GENERATE STABLE ENTITY ID
# --------------------------------------------------

def generate_entity_id(
    source_id: str,
    source_record_id: str
) -> str:
    """
    Generate a deterministic identity from:

        source_id + source_record_id

    The same source record will therefore receive
    the same entity identity each time it is processed.
    """

    source = clean_identifier(
        source_id
    )

    record = clean_identifier(
        source_record_id
    )

    if not source:
        raise ValueError(
            "source_id is required."
        )

    if not record:
        raise ValueError(
            "source_record_id is required."
        )

    identity_key = (
        f"{source}:{record}"
    )

    digest = hashlib.sha256(
        identity_key.encode("utf-8")
    ).hexdigest()

    return f"ENT-{digest[:20]}"


# --------------------------------------------------
# BUILD IDENTITY
# --------------------------------------------------

def resolve_identity(
    source_id: str,
    source_record_id: str,
    entity_type: str
) -> dict:
    """
    Resolve a source record into a stable Octopus identity.

    Important:
    We do not merge records from different sources merely
    because their names look similar. Identity must be
    supported by a source record identifier or an approved
    cross-source identity key.
    """

    entity_id = generate_entity_id(
        source_id,
        source_record_id
    )

    return {
        "entity_id": entity_id,
        "source_id": clean_identifier(
            source_id
        ),
        "source_record_id": clean_identifier(
            source_record_id
        ),
        "entity_type": entity_type
    }


# --------------------------------------------------
# BUILD SOURCE RECORD
# --------------------------------------------------

def build_identity_record(
    source_id: str,
    source_record_id: str,
    entity_type: str,
    entity_name=None,
    location=None,
    status=None,
    attributes=None
) -> dict:
    """
    Create a complete identity-aware record
    ready for the central data layer.
    """

    identity = resolve_identity(
        source_id=source_id,
        source_record_id=source_record_id,
        entity_type=entity_type
    )

    return {
        **identity,
        "entity_name": entity_name,
        "location": location,
        "status": status,
        "attributes": attributes or {}
    }


# --------------------------------------------------
# CHECK IDENTITY CONSISTENCY
# --------------------------------------------------

def same_identity(
    source_id_a: str,
    source_record_id_a: str,
    source_id_b: str,
    source_record_id_b: str
) -> bool:
    """
    Check whether two records represent the exact
    same source identity.
    """

    return (
        clean_identifier(source_id_a)
        == clean_identifier(source_id_b)
        and
        clean_identifier(source_record_id_a)
        == clean_identifier(source_record_id_b)
    )