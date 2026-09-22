# ==========================================================
# PROJECT OCTOPUS — MYSQL CONNECTOR
# Pandas / NumPy free implementation
# ==========================================================

from hashlib import sha256

from sqlalchemy import create_engine, text

from connectors.base_connector import BaseConnector


class MySQLConnector(BaseConnector):
    """
    MySQL source connector.

    Uses SQLAlchemy + PyMySQL and returns ordinary
    Python dictionaries instead of Pandas DataFrames.
    """

    def __init__(self, config: dict):

        super().__init__(config)

        self.config = config

        self.engine = None

        self.connected = False

    # ------------------------------------------------------
    # BUILD DATABASE ENGINE
    # ------------------------------------------------------

    def _build_engine(self):

        if self.engine is not None:

            return self.engine

        host = self.config.get(
            "host",
            "localhost",
        )

        port = self.config.get(
            "port",
            3306,
        )

        username = self.config.get(
            "username",
            "",
        )

        password = self.config.get(
            "password",
            "",
        )

        database = self.config.get(
            "database",
            "",
        )

        connection_url = (
            f"mysql+pymysql://"
            f"{username}:{password}"
            f"@{host}:{port}/{database}"
        )

        self.engine = create_engine(
            connection_url,
            pool_pre_ping=True,
        )

        return self.engine

    # ------------------------------------------------------
    # CONNECT
    # ------------------------------------------------------

    def connect(self) -> None:

        engine = self._build_engine()

        with engine.connect() as connection:

            connection.execute(
                text("SELECT 1")
            )

        self.connected = True

    # ------------------------------------------------------
    # TEST CONNECTION
    # ------------------------------------------------------

    def test_connection(self) -> bool:

        try:

            self.connect()

            return True

        except Exception:

            self.connected = False

            return False

    # ------------------------------------------------------
    # DISCOVER
    # ------------------------------------------------------

    def discover(self) -> dict:

        if not self.connected:
            self.connect()

        table = self.config.get(
            "table"
        )

        if not table:

            raise ValueError(
                "MySQL source requires a table name "
                "for discovery."
            )

        engine = self._build_engine()

        with engine.connect() as connection:

            result = connection.execute(
                text(
                    f"SELECT * FROM `{table}` LIMIT 1"
                )
            )

            columns = list(
                result.keys()
            )

        return {
            "source_type": "MySQL",
            "table": table,
            "columns": columns,
            "column_count": len(
                columns
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

        query = self.config.get(
            "query"
        )

        table = (
            target
            or self.config.get(
                "table"
            )
        )

        if not query:

            if not table:

                raise ValueError(
                    "MySQL source requires either "
                    "'query' or 'table'."
                )

            query = (
                f"SELECT * FROM `{table}`"
            )

        engine = self._build_engine()

        rows = []

        with engine.connect() as connection:

            result = connection.execute(
                text(query)
            )

            columns = list(
                result.keys()
            )

            for record in result.fetchall():

                row = {}

                for index, column in enumerate(
                    columns
                ):

                    value = record[index]

                    if value is not None:

                        if isinstance(
                            value,
                            (
                                str,
                                int,
                                float,
                                bool,
                            ),
                        ):

                            pass

                        elif hasattr(
                            value,
                            "isoformat",
                        ):

                            value = value.isoformat()

                        else:

                            value = str(
                                value
                            )

                    row[column] = value

                rows.append(
                    row
                )

        return rows

    # ------------------------------------------------------
    # SOURCE INFORMATION
    # ------------------------------------------------------

    def get_source_info(self) -> dict:

        host = self.config.get(
            "host",
            "localhost",
        )

        port = self.config.get(
            "port",
            3306,
        )

        database = self.config.get(
            "database",
            "",
        )

        table = self.config.get(
            "table",
            "",
        )

        source_key = (
            f"MYSQL:"
            f"{host}:"
            f"{port}:"
            f"{database}:"
            f"{table}"
        )

        source_hash = sha256(
            source_key.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        info = super().get_source_info()

        info.update(
            {
                "source_id": (
                    f"SRC-{source_hash}"
                ),
                "source_type": "MySQL",
                "source_name": (
                    f"MySQL:{database}"
                ),
                "connection_reference": (
                    f"{host}:{port}/{database}"
                ),
                "table": table,
            }
        )

        return info

    # ------------------------------------------------------
    # CLOSE
    # ------------------------------------------------------

    def close(self) -> None:

        if self.engine is not None:

            try:

                self.engine.dispose()

            except Exception:

                pass

        self.engine = None

        self.connected = False