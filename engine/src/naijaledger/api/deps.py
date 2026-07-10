"""FastAPI dependencies for the public API."""

from collections.abc import Generator

from sqlalchemy.engine import Connection, Engine

from naijaledger.config import load_settings
from naijaledger.db.connection import create_db_engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_db_engine(load_settings().database_url)
    return _engine


def get_connection() -> Generator[Connection, None, None]:
    with get_engine().connect() as connection:
        yield connection
