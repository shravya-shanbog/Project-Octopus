# ==================================================
# PROJECT OCTOPUS — DATABASE MIGRATIONS
# ==================================================

from database.connection import Base, engine

# Import every model so SQLAlchemy registers
# all Project Octopus tables.
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


def initialize_database():
    """
    Create all Project Octopus tables that
    do not already exist.
    """

    Base.metadata.create_all(
        bind=engine
    )


if __name__ == "__main__":

    initialize_database()

    print(
        "Project Octopus universal database "
        "initialized successfully."
    )