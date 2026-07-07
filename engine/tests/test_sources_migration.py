import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


def _database_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url and url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _alembic_config(database_url: str) -> Config:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = Config(os.path.join(root, "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    database_url = _database_url()
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    engine = create_engine(database_url)
    command.downgrade(_alembic_config(database_url), "base")
    command.upgrade(_alembic_config(database_url), "head")

    yield engine

    command.downgrade(_alembic_config(database_url), "base")
    engine.dispose()


def test_sources_unique_url_format(db_engine: Engine) -> None:
    insert_sql = text(
        """
        INSERT INTO sources (
            name, jurisdiction, category, url, fetch_method, format
        ) VALUES (
            :name, :jurisdiction, :category, :url, :fetch_method, :format
        )
        """
    )
    row = {
        "name": "NOCOPO",
        "jurisdiction": "federal",
        "category": "procurement",
        "url": "https://nocopo.bpp.gov.ng/",
        "fetch_method": "http",
        "format": "html",
    }

    with db_engine.begin() as connection:
        connection.execute(insert_sql, row)

    with db_engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(insert_sql, row)


def test_sources_defaults(db_engine: Engine) -> None:
    insert_sql = text(
        """
        INSERT INTO sources (
            name, jurisdiction, category, url, fetch_method, format
        ) VALUES (
            'Open Treasury', 'federal', 'payments',
            'https://payment.gov.ng/', 'http', 'html'
        )
        RETURNING status, reliability_score, health_status
        """
    )

    with db_engine.begin() as connection:
        result = connection.execute(insert_sql).one()

    assert result.status == "proposed"
    assert float(result.reliability_score) == 0.0
    assert result.health_status == "unknown"
