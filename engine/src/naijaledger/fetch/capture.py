import logging
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID

from minio import Minio
from sqlalchemy.engine import Connection

from naijaledger.archive.storage import store_raw_bytes
from naijaledger.documents.format import infer_document_format
from naijaledger.documents.service import upsert_document_from_fetch
from naijaledger.fetch.service import create_fetch_record
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import record_fetch_success

logger = logging.getLogger("naijaledger.fetch")


class FetchCaptureResult(TypedDict):
    fetch_record_id: UUID
    ok: bool
    archive_key: str | None
    content_hash: str | None
    document_id: UUID | None


class FetchBatchSummary(TypedDict):
    attempted: int
    succeeded: int
    failed: int


def fetch_ok(status_code: int | None) -> bool:
    if status_code is None:
        return False
    return 200 <= status_code < 400


def persist_fetch_capture(
    connection: Connection,
    source: SourceRecord,
    *,
    url: str,
    requested_at: datetime,
    status_code: int | None,
    body: bytes | None,
    headers: dict[str, str] | None,
    error: str | None,
    minio_client: Minio,
    bucket: str,
) -> FetchCaptureResult:
    if error is not None or body is None:
        record = create_fetch_record(
            connection,
            source_id=source.id,
            url=url,
            requested_at=requested_at,
            status_code=status_code,
            ok=False,
            byte_count=None,
            sha256=None,
            headers=headers,
            error=error or "no response body",
            archive_key=None,
        )
        logger.warning("fetch failed for %s (%s): %s", source.name, url, error or "no body")
        return FetchCaptureResult(
            fetch_record_id=record.id,
            ok=False,
            archive_key=None,
            content_hash=None,
            document_id=None,
        )

    archived = store_raw_bytes(
        minio_client,
        bucket,
        body,
        content_type=(headers or {}).get("content-type", "application/octet-stream"),
    )
    archive_key = archived["archive_key"]
    content_hash = archived["content_hash"]
    ok = fetch_ok(status_code)

    record = create_fetch_record(
        connection,
        source_id=source.id,
        url=url,
        requested_at=requested_at,
        status_code=status_code,
        ok=ok,
        byte_count=len(body),
        sha256=content_hash,
        headers=headers,
        error=None if ok else f"HTTP {status_code}",
        archive_key=archive_key,
    )

    document_id: UUID | None = None
    if ok:
        document_format = infer_document_format(
            url=url,
            content_type=(headers or {}).get("content-type"),
            source_format=source.format,
        )
        upsert = upsert_document_from_fetch(
            connection,
            source_id=source.id,
            first_fetch_id=record.id,
            sha256=content_hash,
            archive_key=archive_key,
            format=document_format,
        )
        document_id = upsert["document_id"]
        record_fetch_success(
            connection,
            source.id,
            fetched_at=requested_at,
            content_hash=content_hash,
        )
        logger.info(
            "fetch archived %s (%s) -> %s (%d bytes, document %s)",
            source.name,
            url,
            archive_key,
            len(body),
            document_id,
        )
    else:
        logger.warning(
            "fetch non-success %s (%s): HTTP %s",
            source.name,
            url,
            status_code,
        )

    return FetchCaptureResult(
        fetch_record_id=record.id,
        ok=ok,
        archive_key=archive_key,
        content_hash=content_hash,
        document_id=document_id,
    )


def empty_batch_summary() -> FetchBatchSummary:
    return {"attempted": 0, "succeeded": 0, "failed": 0}


def record_batch_result(summary: FetchBatchSummary, result: FetchCaptureResult) -> None:
    summary["attempted"] += 1
    if result["ok"]:
        summary["succeeded"] += 1
    else:
        summary["failed"] += 1


def now_utc() -> datetime:
    return datetime.now(tz=UTC)
