from naijaledger.db.connection import DEFAULT_DATABASE_URL, resolve_database_url


def test_resolve_database_url_prefers_explicit_value() -> None:
    assert (
        resolve_database_url("postgresql://example.com/db") == "postgresql+psycopg://example.com/db"
    )


def test_resolve_database_url_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert resolve_database_url() == DEFAULT_DATABASE_URL
