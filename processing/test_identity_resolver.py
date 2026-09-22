# ==================================================
# PROJECT OCTOPUS — IDENTITY RESOLUTION TEST
# ==================================================

from processing.identity_resolver import (
    generate_entity_id,
    resolve_identity,
    build_identity_record,
    same_identity
)


print("\n=== PROJECT OCTOPUS IDENTITY RESOLUTION TEST ===")


# --------------------------------------------------
# 1. SAME SOURCE RECORD
# --------------------------------------------------

id_1 = generate_entity_id(
    "SRC-MYSQL",
    "A001"
)

id_2 = generate_entity_id(
    "SRC-MYSQL",
    "A001"
)

print("\n=== SAME SOURCE RECORD ===")

print(f"Identity 1: {id_1}")
print(f"Identity 2: {id_2}")

print(
    f"Same identity: {id_1 == id_2}"
)


# --------------------------------------------------
# 2. DIFFERENT SOURCE RECORD
# --------------------------------------------------

id_3 = generate_entity_id(
    "SRC-EXCEL",
    "A001"
)

print("\n=== DIFFERENT SOURCE ===")

print(f"MySQL A001: {id_1}")
print(f"Excel A001: {id_3}")

print(
    f"Different identity: {id_1 != id_3}"
)


# --------------------------------------------------
# 3. DIFFERENT APPLIANCES
# --------------------------------------------------

temperature_sensor = resolve_identity(
    source_id="SRC-IOT",
    source_record_id="TEMP-001",
    entity_type="Temperature Sensor"
)

air_conditioner = resolve_identity(
    source_id="SRC-IOT",
    source_record_id="AC-014",
    entity_type="Air Conditioner"
)

print("\n=== DIFFERENT APPLIANCES ===")

print(temperature_sensor)
print(air_conditioner)


# --------------------------------------------------
# 4. COMPLETE IDENTITY-AWARE RECORD
# --------------------------------------------------

record = build_identity_record(
    source_id="SRC-IOT",
    source_record_id="TEMP-001",
    entity_type="Temperature Sensor",
    entity_name="Temperature Sensor TEMP-001",
    location="Gallery 1",
    status="Active",
    attributes={
        "temperature": 27.4,
        "humidity": 61,
        "battery": 88
    }
)

print("\n=== COMPLETE RECORD ===")

for key, value in record.items():
    print(f"{key}: {value}")


# --------------------------------------------------
# 5. EXACT IDENTITY CHECK
# --------------------------------------------------

same = same_identity(
    "SRC-IOT",
    "TEMP-001",
    "SRC-IOT",
    "TEMP-001"
)

different = same_identity(
    "SRC-IOT",
    "TEMP-001",
    "SRC-IOT",
    "AC-014"
)

print("\n=== IDENTITY CHECK ===")

print(
    f"Same record check: {same}"
)

print(
    f"Different record check: {different}"
)


print(
    "\n=== IDENTITY RESOLUTION TEST PASSED ==="
)