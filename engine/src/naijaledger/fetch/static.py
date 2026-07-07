import logging
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID

import httpx
from minio import Minio
from sqlalchemy.engine import Connection

from naijaledger.archive.storage import store_raw_bytes
from naijaledger.fetch.service import create_fetch_record
from naijaledger.http.client import create_http_client
from naijaledger.sources.health import validate_probe_url
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import list_sources, record_fetch_success

logger = logging.getLogger("naijaledger.fetch")


class StaticFetchResult(TypedDict):
    fetch_record_id: UUID
    ok: bool
    archive_key: str | None
    content_hash: str | None


class StaticFetchSummary(TypedDict):
    attempted: int
    succeeded: int
    failed: int


def _response_headers(response: httpx.Response) -> dict[str, str]:
    return {key: value for key, value in response.headers.items()}


def _fetch_ok(status_code: int | None) -> bool:
    if status_code is None:
        return False
    return 200 <= status_code < 400


def static_fetch_source(
    connection: Connection,
    source: SourceRecord,
    *,
    http_client: httpx.Client,
    minio_client: Minio,
    bucket: str,
    requested_at: datetime | None = None,
) -> StaticFetchResult:
    if source.fetch_method != "http":
        msg = f"static fetch only supports http sources (got {source.fetch_method})"
        raise ValueError(msg)

    when = requested_at or datetime.now(tz=UTC)
    url = source.url
    validate_probe_url(url)

    status_code: int | None = None
    body: bytes | None = None
    headers: dict[str, str] | None = None
    error: str | None = None
    archive_key: str | None = None
    content_hash: str | None = None

    try:
        response = http_client.get(url, follow_redirects=True)
        status_code = response.status_code
        body = response.content
        headers = _response_headers(response)
    except httpx.HTTPError as exc:
        error = str(exc)
        record = create_fetch_record(
            connection,
            source_id=source.id,
            url=url,
            requested_at=when,
            status_code=None,
            ok=False,
            byte_count=None,
            sha256=None,
            headers=None,
            error=error,
            archive_key=None,
        )
        logger.warning("fetch failed for %s (%s): %s", source.name, url, error)
        return StaticFetchResult(
            fetch_record_id=record.id,
            ok=False,
            archive_key=None,
            content_hash=None,
        )

    archived = store_raw_bytes(
        minio_client,
        bucket,
        body,
        content_type=headers.get("content-type", "application/octet-stream"),
    )
    archive_key = archived["archive_key"]
    content_hash = archived["content_hash"]
    ok = _fetch_ok(status_code)

    record = create_fetch_record(
        connection,
        source_id=source.id,
        url=url,
        requested_at=when,
        status_code=status_code,
        ok=ok,
        byte_count=len(body),
        sha256=content_hash,
        headers=headers,
        error=None if ok else f"HTTP {status_code}",
        archive_key=archive_key,
    )

    if ok:
        record_fetch_success(
            connection,
            source.id,
            fetched_at=when,
            content_hash=content_hash,
        )
        logger.info(
            "fetch archived %s (%s) -> %s (%d bytes)",
            source.name,
            url,
            archive_key,
            len(body),
        )
    else:
        logger.warning(
            "fetch non-success %s (%s): HTTP %s",
            source.name,
            url,
            status_code,
        )

    return StaticFetchResult(
        fetch_record_id=record.id,
        ok=ok,
        archive_key=archive_key,
        content_hash=content_hash,
    )


def run_static_fetch_for_approved_http_sources(
    connection: Connection,
    *,
    http_client: httpx.Client | None = None,
    minio_client: Minio | None = None,
    bucket: str,
    requested_at: datetime | None = None,
) -> StaticFetchSummary:
    owned_client = http_client is None
    client = http_client or create_http_client()

    summary: StaticFetchSummary = {"attempted": 0, "succeeded": 0, "failed": 0}
    sources = [
        source
        for source in list_sources(connection, status="approved")
        if source.fetch_method == "http"
    ]

    try:
        for source in sources:
            if minio_client is None:
                msg = "minio_client is required"
                raise ValueError(msg)
            result = static_fetch_source(
                connection,
                source,
                http_client=client,
                minio_client=minio_client,
                bucket=bucket,
                requested_at=requested_at,
            )
            summary["attempted"] += 1
            if result["ok"]:
                summary["succeeded"] += 1
            else:
                summary["failed"] += 1
    finally:
        if owned_client:
            client.close()

    return summary
