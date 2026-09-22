# ==================================================
# PROJECT OCTOPUS — DATABASE CONNECTION
# ==================================================

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


# --------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

load_dotenv()


# --------------------------------------------------
# DATABASE URL
# --------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./octopus.db"
)


# --------------------------------------------------
# DATABASE ENGINE
# --------------------------------------------------

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)


# --------------------------------------------------
# BASE MODEL
# --------------------------------------------------

class Base(DeclarativeBase):
    pass


# --------------------------------------------------
# DATABASE SESSION
# --------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# --------------------------------------------------
# DATABASE DEPENDENCY
# --------------------------------------------------

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()