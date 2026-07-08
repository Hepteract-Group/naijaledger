import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import create_source


def test_documents_table_exists(db_connection) -> None:
    row = db_connection.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'documents'
            ORDER BY ordinal_position
            """
        )
    ).all()
    columns = [record[0] for record in row]
    assert "source_id" in columns
    assert "first_fetch_id" in columns
    assert "sha256" in columns
    assert "archive_key" in columns
    assert "format" in columns


def test_documents_unique_sha256(db_connection) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Documents Migration Test",
            jurisdiction="federal",
            category="procurement",
            url="https://example.com/doc",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    fetch_id = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, 'hash-a', 'sha256/hash-a'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "url": source.url},
    ).scalar_one()

    db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key
            ) VALUES (
                :source_id, :fetch_id, 'hash-a', 'html', 'sha256/hash-a'
            )
            """
        ),
        {"source_id": source.id, "fetch_id": fetch_id},
    )

    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        source_id, first_fetch_id, sha256, format, archive_key
                    ) VALUES (
                        :source_id, :fetch_id, 'hash-a', 'html', 'sha256/hash-a'
                    )
                    """
                ),
                {"source_id": source.id, "fetch_id": fetch_id},
            )
