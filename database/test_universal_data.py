# ==================================================
# PROJECT OCTOPUS — UNIVERSAL DATA TEST
# ==================================================

from datetime import datetime

from database.connection import SessionLocal
from database.repository import (
    create_source,
    get_source,
    upsert_entity,
    create_entity_data,
    create_event
)


db = SessionLocal()


try:

    print("\n=== PROJECT OCTOPUS UNIVERSAL DATA TEST ===")


    # ==================================================
    # 1. CREATE DATA SOURCE
    # ==================================================

    source_data = {
        "source_id": "SRC-001",
        "source_name": "Appliance Test Source",
        "source_type": "Test API"
    }

    source = get_source(
        db,
        "SRC-001"
    )

    if source is None:

        create_source(
            db,
            source_data
        )

        print("\nSource created successfully.")

    else:

        print("\nSource already exists.")


    # ==================================================
    # 2. APPLIANCE A — TEMPERATURE DEVICE
    # ==================================================

    entity_a = {
        "entity_id": "DEVICE-A001",
        "entity_type": "Temperature Sensor",
        "entity_name": "Temperature Sensor A001",
        "source_id": "SRC-001",
        "location": "Gallery 1",
        "status": "Active",
        "attributes": {
            "manufacturer": "Test Manufacturer",
            "model": "TS-100"
        }
    }

    upsert_entity(
        db,
        entity_a
    )


    create_entity_data(
        db,
        {
            "entity_id": "DEVICE-A001",
            "source_id": "SRC-001",
            "schema_version": "1.0",
            "payload": {
                "temperature": 27.4,
                "humidity": 61,
                "battery": 88
            },
            "observed_at": datetime(
                2026, 9, 8, 12, 30
            )
        }
    )


    # ==================================================
    # 3. APPLIANCE B — AIR CONDITIONER
    # ==================================================

    entity_b = {
        "entity_id": "DEVICE-B014",
        "entity_type": "Air Conditioner",
        "entity_name": "Air Conditioner B014",
        "source_id": "SRC-001",
        "location": "Room 4",
        "status": "Active",
        "attributes": {
            "manufacturer": "Test Manufacturer",
            "model": "AC-500"
        }
    }

    upsert_entity(
        db,
        entity_b
    )


    create_entity_data(
        db,
        {
            "entity_id": "DEVICE-B014",
            "source_id": "SRC-001",
            "schema_version": "1.0",
            "payload": {
                "mode": "cooling",
                "fan_speed": 3,
                "set_point": 22,
                "power_kw": 1.8
            },
            "observed_at": datetime(
                2026, 9, 8, 12, 31
            )
        }
    )


    print("\nDifferent appliance data stored successfully.")


    # ==================================================
    # 4. TOUCH / INTERACTION EVENT
    # ==================================================

    create_event(
        db,
        {
            "event_id": "EVENT-0001",
            "entity_id": "DEVICE-A001",
            "event_type": "TOUCHED",
            "actor_id": "USER-027",
            "actor_type": "user",
            "location": "Gallery 1",
            "source_id": "SRC-001",
            "occurred_at": datetime(
                2026, 9, 8, 12, 32, 15
            ),
            "event_metadata": {
                "interaction_method": "touch",
                "description": "Device interaction detected"
            }
        }
    )


    print(
        "Interaction event stored successfully."
    )


    # ==================================================
    # 5. SECOND EVENT
    # ==================================================

    create_event(
        db,
        {
            "event_id": "EVENT-0002",
            "entity_id": "DEVICE-B014",
            "event_type": "STATUS_CHANGED",
            "actor_id": "SYSTEM",
            "actor_type": "system",
            "location": "Room 4",
            "source_id": "SRC-001",
            "occurred_at": datetime(
                2026, 9, 8, 12, 33, 10
            ),
            "event_metadata": {
                "old_status": "Active",
                "new_status": "Maintenance"
            }
        }
    )


    print(
        "Status-change event stored successfully."
    )


    print(
        "\n=== UNIVERSAL DATA TEST PASSED ==="
    )

    print(
        "\nThe database now contains:"
    )

    print(
        "1. Multiple appliance/entity types"
    )

    print(
        "2. Different data structures per entity"
    )

    print(
        "3. Identity-based separation"
    )

    print(
        "4. Interaction/event records"
    )


finally:

    db.close()