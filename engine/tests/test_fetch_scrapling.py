from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from naijaledger.archive.types import ArchiveStoreResult
from naijaledger.fetch.scrapling_fetch import (
    ScraplingPageResult,
    scrapling_fetch_source,
)
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source, get_source


def test_scrapling_fetch_source_success(db_connection, monkeypatch: pytest.MonkeyPatch) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Lagos OCDS",
            jurisdiction="state",
            region="Lagos",
            category="procurement",
            url="https://lagos.example/ocds",
            fetch_method="scrapling",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")
    minio_client = MagicMock()

    def fake_scrapling(_url: str, *, settings: object = None) -> ScraplingPageResult:
        return ScraplingPageResult(
            status_code=200,
            body=b"<html>ocds portal</html>",
            headers={"content-type": "text/html"},
            error=None,
        )

    def fake_store(
        _client: object,
        _bucket: str,
        data: bytes,
        **kwargs: object,
    ) -> ArchiveStoreResult:
        return ArchiveStoreResult(
            archive_key="sha256/scrapling",
            content_hash="scrapling",
            byte_count=len(data),
            created=True,
        )

    monkeypatch.setattr(
        "naijaledger.fetch.scrapling_fetch.fetch_url_with_scrapling",
        fake_scrapling,
    )
    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", fake_store)

    result = scrapling_fetch_source(
        db_connection,
        approved,
        minio_client=minio_client,
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 7, 12, 0, tzinfo=UTC),
    )

    assert result["ok"] is True
    updated = get_source(db_connection, approved.id)
    assert updated.last_success_hash == "scrapling"


def test_scrapling_fetch_source_rejects_http_method(db_connection) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="HTTP only",
            jurisdiction="federal",
            category="budget",
            url="https://example.com/budget",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")

    with pytest.raises(ValueError, match="scrapling fetch only supports"):
        scrapling_fetch_source(
            db_connection,
            approved,
            minio_client=MagicMock(),
            bucket="test-bucket",
        )
