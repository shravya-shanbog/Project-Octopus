# ==========================================================
# PROJECT OCTOPUS — CSV CONNECTOR
# Pandas / NumPy free implementation
# ==========================================================

from pathlib import Path
import csv
import hashlib

from connectors.base_connector import BaseConnector


class CSVConnector(BaseConnector):
    """
    Connector for CSV data sources.

    Uses Python's built-in csv module so the
    Octopus backend does not depend on Pandas/NumPy.
    """

    def __init__(self, config: dict):

        super().__init__(config)

        self.file_path = Path(
            config.get("file_path", "")
        )

        self.rows = []

    # ------------------------------------------------------
    # CONNECT
    # ------------------------------------------------------

    def connect(self) -> None:

        if not self.file_path:

            raise ValueError(
                "CSV file path is required."
            )

        if not self.file_path.exists():

            raise FileNotFoundError(
                f"CSV file not found: {self.file_path}"
            )

        if self.file_path.suffix.lower() != ".csv":

            raise ValueError(
                "The selected file is not a CSV file."
            )

        self.connected = True

    # ------------------------------------------------------
    # TEST CONNECTION
    # ------------------------------------------------------

    def test_connection(self) -> bool:

        try:

            self.connect()

            with self.file_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as file:

                reader = csv.reader(file)

                next(
                    reader,
                    None,
                )

            return True

        except Exception:

            return False

    # ------------------------------------------------------
    # DISCOVER
    # ------------------------------------------------------

    def discover(self) -> dict:

        if not self.connected:
            self.connect()

        rows = self.extract()

        columns = []

        if rows:

            columns = list(
                rows[0].keys()
            )

        return {
            "file_name": self.file_path.name,
            "file_path": str(
                self.file_path
            ),
            "source_type": "CSV",
            "columns": columns,
            "column_count": len(
                columns
            ),
            "row_count": len(
                rows
            ),
        }

    # ------------------------------------------------------
    # EXTRACT
    # ------------------------------------------------------

    def extract(
        self,
        target=None,
    ) -> list[dict]:

        if not self.connected:
            self.connect()

        rows = []

        with self.file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(
                file
            )

            if not reader.fieldnames:

                raise ValueError(
                    "CSV file does not contain a header row."
                )

            headers = []

            for header in reader.fieldnames:

                if header is None:

                    continue

                cleaned_header = str(
                    header
                ).strip()

                headers.append(
                    cleaned_header
                )

            for raw_row in reader:

                row = {}

                for header in headers:

                    value = raw_row.get(
                        header
                    )

                    if isinstance(
                        value,
                        str,
                    ):

                        value = value.strip()

                    row[header] = value

                # Ignore completely empty rows
                if any(
                    value not in (
                        None,
                        "",
                    )
                    for value in row.values()
                ):

                    rows.append(row)

        self.rows = rows

        return rows

    # ------------------------------------------------------
    # SOURCE INFORMATION
    # ------------------------------------------------------

    def get_source_info(self) -> dict:

        path_value = str(
            self.file_path.resolve()
        )

        source_hash = hashlib.sha256(
            path_value.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        info = super().get_source_info()

        info.update(
            {
                "source_id": (
                    f"SRC-{source_hash}"
                ),
                "source_type": "CSV",
                "source_name": (
                    self.file_path.name
                ),
                "file_name": (
                    self.file_path.name
                ),
                "file_path": path_value,
                "connection_reference": (
                    path_value
                ),
            }
        )

        return info

    # ------------------------------------------------------
    # CLOSE
    # ------------------------------------------------------

    def close(self) -> None:

        self.rows = []

        self.connected = False