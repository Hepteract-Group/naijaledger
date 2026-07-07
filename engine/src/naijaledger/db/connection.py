import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_db_engine(database_url: str | None = None) -> Engine:
    resolved = database_url or os.environ.get("DATABASE_URL")
    if not resolved:
        msg = "DATABASE_URL is required"
        raise ValueError(msg)
    return create_engine(make_url(normalize_database_url(resolved)))
