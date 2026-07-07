import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, Engine

from naijaledger.db.connection import create_db_engine, normalize_database_url


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _alembic_config(database_url: str) -> Config:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = Config(os.path.join(root, "alembic.ini"))
    config.set_main_option("sqlalchemy.url", normalize_database_url(database_url))
    return config


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    database_url = _database_url()
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    engine = create_db_engine(database_url)
    command.downgrade(_alembic_config(database_url), "base")
    command.upgrade(_alembic_config(database_url), "head")

    yield engine

    command.downgrade(_alembic_config(database_url), "base")
    engine.dispose()


@pytest.fixture
def db_connection(db_engine: Engine) -> Generator[Connection, None, None]:
    with db_engine.connect() as connection:
        with connection.begin():
            yield connection
