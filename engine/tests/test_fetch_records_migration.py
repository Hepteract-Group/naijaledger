import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_fetch_records_table_exists(db_connection) -> None:
    row = db_connection.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'fetch_records'
            ORDER BY ordinal_position
            """
        )
    ).all()
    columns = [record[0] for record in row]
    assert "source_id" in columns
    assert "archive_key" in columns
    assert "sha256" in columns


def test_fetch_records_foreign_key_to_sources(db_connection) -> None:
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO fetch_records (
                        source_id, url, requested_at, status_code, ok
                    ) VALUES (
                        gen_random_uuid(), 'https://example.com', now(), 200, true
                    )
                    """
                )
            )
