import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

DEFAULT_DATABASE_URL = "postgresql+psycopg://naijaledger:naijaledger@localhost:5432/naijaledger"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def resolve_database_url(database_url: str | None = None) -> str:
    raw = database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
    return normalize_database_url(raw)


def create_db_engine(database_url: str | None = None) -> Engine:
    return create_engine(make_url(resolve_database_url(database_url)))
