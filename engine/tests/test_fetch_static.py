from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest

from naijaledger.archive.types import ArchiveStoreResult
from naijaledger.fetch.service import create_fetch_record, get_fetch_record
from naijaledger.fetch.static import static_fetch_source
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source, get_source


def test_create_and_get_fetch_record(db_connection) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Fetch Record Test",
            jurisdiction="federal",
            category="procurement",
            url="https://example.com/data",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    when = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)
    created = create_fetch_record(
        db_connection,
        source_id=source.id,
        url=source.url,
        requested_at=when,
        status_code=200,
        ok=True,
        byte_count=12,
        sha256="abc123",
        headers={"content-type": "text/html"},
        error=None,
        archive_key="sha256/abc123",
    )
    loaded = get_fetch_record(db_connection, created.id)
    assert loaded.source_id == source.id
    assert loaded.ok is True
    assert loaded.archive_key == "sha256/abc123"
    assert loaded.headers == {"content-type": "text/html"}


def test_static_fetch_source_success(db_connection, monkeypatch: pytest.MonkeyPatch) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Static Fetch OK",
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
        requested_at=datetime(2026, 7, 7, 12, 0, tzinfo=UTC),
    )

    assert result["ok"] is True
    assert result["archive_key"] == "sha256/deadbeef"
    assert result["document_id"] is not None
    record = get_fetch_record(db_connection, result["fetch_record_id"])
    assert record.byte_count == len(b"<html>payments</html>")
    assert record.sha256 == "deadbeef"

    updated_source = get_source(db_connection, approved.id)
    assert updated_source.last_success_hash == "deadbeef"
    assert updated_source.last_fetched_at is not None


def test_static_fetch_source_connection_error(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Static Fetch Fail",
            jurisdiction="federal",
            category="budget",
            url="https://example.com/budget",
            fetch_method="http",
            format="pdf",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    minio_client = MagicMock()
    store_called = {"value": False}

    def fake_store(*_args: object, **_kwargs: object) -> ArchiveStoreResult:
        store_called["value"] = True
        return ArchiveStoreResult(
            archive_key="sha256/nope",
            content_hash="nope",
            byte_count=0,
            created=True,
        )

    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", fake_store)

    result = static_fetch_source(
        db_connection,
        approved,
        http_client=http_client,
        minio_client=minio_client,
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 7, 12, 0, tzinfo=UTC),
    )

    assert result["ok"] is False
    assert result["archive_key"] is None
    assert result["document_id"] is None
    assert store_called["value"] is False
    record = get_fetch_record(db_connection, result["fetch_record_id"])
    assert record.error is not None
    assert record.archive_key is None
