# ==================================================
# PROJECT OCTOPUS — SCHEMA MAPPER TEST
# ==================================================

from processing.extractor import extract_file
from processing.schema_mapper import map_dataframe


file_path = "data/samples/test_inventory.csv"


dataframe = extract_file(
    file_path
)


results = map_dataframe(
    dataframe
)


print("\n=== PROJECT OCTOPUS SCHEMA MAPPING TEST ===\n")


for result in results:

    print(
        f"{result['source_column']}"
        f"  -->  "
        f"{result['canonical_field']}"
        f"  |  "
        f"Confidence: "
        f"{result['confidence']}"
        f"  |  "
        f"{result['decision']}"
    )