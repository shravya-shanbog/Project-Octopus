from processing.extractor import extract_file
from processing.extractor import inspect_extracted_data


file_path = "data/samples/test_inventory.csv"


dataframe = extract_file(
    file_path
)


inspection = inspect_extracted_data(
    dataframe
)


print("\n=== PROJECT OCTOPUS EXTRACTOR TEST ===")

print(
    f"Rows extracted: {inspection['row_count']}"
)

print(
    f"Columns detected: {inspection['column_count']}"
)

print(
    f"Columns: {inspection['columns']}"
)

print(
    f"Empty rows: {inspection['empty_rows']}"
)

print("\n=== FIRST RECORDS ===")

print(
    dataframe.head()
)