from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import text

from naijaledger.archive.types import ArchiveStoreResult
from naijaledger.documents.format import infer_document_format
from naijaledger.documents.service import get_document, upsert_document_from_fetch
from naijaledger.fetch.capture import persist_fetch_capture
from naijaledger.fetch.service import create_fetch_record
from naijaledger.fetch.static import static_fetch_source
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source


@pytest.mark.parametrize(
    ("content_type", "url", "source_format", "expected"),
    [
        ("text/html; charset=utf-8", "https://example.com/data", "json", "html"),
        ("application/pdf", "https://example.com/page", "html", "pdf"),
        (None, "https://example.com/report.pdf", "html", "pdf"),
        (None, "https://example.com/data.json", "html", "json"),
        ("application/octet-stream", "https://example.com/page", "xlsx", "xlsx"),
    ],
)
def test_infer_document_format(
    content_type: str | None,
    url: str,
    source_format: str,
    expected: str,
) -> None:
    assert (
        infer_document_format(
            url=url,
            content_type=content_type,
            source_format=source_format,  # type: ignore[arg-type]
        )
        == expected
    )


def test_upsert_document_dedup_by_sha256(db_connection) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Document Dedup",
            jurisdiction="federal",
            category="budget",
            url="https://example.com/budget.pdf",
            fetch_method="http",
            format="pdf",
            added_by=SEED_ADDED_BY,
        ),
    )
    when = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    first_fetch = create_fetch_record(
        db_connection,
        source_id=source.id,
        url=source.url,
        requested_at=when,
        status_code=200,
        ok=True,
        byte_count=100,
        sha256="samehash",
        headers={"content-type": "application/pdf"},
        error=None,
        archive_key="sha256/samehash",
    )
    second_fetch = create_fetch_record(
        db_connection,
        source_id=source.id,
        url=source.url,
        requested_at=when,
        status_code=200,
        ok=True,
        byte_count=100,
        sha256="samehash",
        headers={"content-type": "application/pdf"},
        error=None,
        archive_key="sha256/samehash",
    )

    first = upsert_document_from_fetch(
        db_connection,
        source_id=source.id,
        first_fetch_id=first_fetch.id,
        sha256="samehash",
        archive_key="sha256/samehash",
        format="pdf",
    )
    second = upsert_document_from_fetch(
        db_connection,
        source_id=source.id,
        first_fetch_id=second_fetch.id,
        sha256="samehash",
        archive_key="sha256/samehash",
        format="pdf",
    )

    assert first["created"] is True
    assert second["created"] is False
    assert first["document_id"] == second["document_id"]

    count = db_connection.execute(text("SELECT COUNT(*) FROM documents")).scalar_one()
    assert count == 1

    document = get_document(db_connection, first["document_id"])
    assert document.first_fetch_id == first_fetch.id
    assert document.format == "pdf"


def test_persist_fetch_capture_creates_document(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Capture Document",
            jurisdiction="state",
            category="procurement",
            url="https://example.com/awards",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )

    def fake_store(
        _client: object,
        _bucket: str,
        data: bytes,
        **kwargs: object,
    ) -> ArchiveStoreResult:
        return ArchiveStoreResult(
            archive_key="sha256/cafebabe",
            content_hash="cafebabe",
            byte_count=len(data),
            created=True,
        )

    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", fake_store)

    result = persist_fetch_capture(
        db_connection,
        source,
        url=source.url,
        requested_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
        status_code=200,
        body=b"<html>awards</html>",
        headers={"content-type": "text/html"},
        error=None,
        minio_client=MagicMock(),
        bucket="test-bucket",
    )

    assert result["ok"] is True
    assert result["document_id"] is not None
    document = get_document(db_connection, result["document_id"])
    assert document.sha256 == "cafebabe"
    assert document.archive_key == "sha256/cafebabe"
    assert document.first_fetch_id == result["fetch_record_id"]


def test_persist_fetch_capture_failed_fetch_no_document(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Capture No Document",
            jurisdiction="federal",
            category="budget",
            url="https://example.com/missing",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )

    result = persist_fetch_capture(
        db_connection,
        source,
        url=source.url,
        requested_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
        status_code=None,
        body=None,
        headers=None,
        error="connection refused",
        minio_client=MagicMock(),
        bucket="test-bucket",
    )

    assert result["ok"] is False
    assert result["document_id"] is None
    count = db_connection.execute(text("SELECT COUNT(*) FROM documents")).scalar_one()
    assert count == 0


def test_static_fetch_source_creates_document(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Static Fetch Document",
            jurisdiction="federal",
            category="payments",
            url="https://example.com/treasury",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html>payments</html>",
            headers={"content-type": "text/html"},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    minio_client = MagicMock()

    def fake_store(
        _client: object,
        _bucket: str,
        data: bytes,
        **kwargs: object,
    ) -> ArchiveStoreResult:
        return ArchiveStoreResult(
            archive_key="sha256/deadbeef",
            content_hash="deadbeef",
            byte_count=len(data),
            created=True,
        )

    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", fake_store)

    result = static_fetch_source(
        db_connection,
        approved,
        http_client=http_client,
        minio_client=minio_client,
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
    )

    assert result["ok"] is True
    assert result["document_id"] is not None
    document = get_document(db_connection, result["document_id"])
    assert document.format == "html"
