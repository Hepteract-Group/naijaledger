import logging
from datetime import datetime

import httpx
from minio import Minio
from sqlalchemy.engine import Connection

from naijaledger.fetch.capture import (
    FetchBatchSummary,
    FetchCaptureResult,
    empty_batch_summary,
    now_utc,
    persist_fetch_capture,
    record_batch_result,
)
from naijaledger.http.client import create_http_client
from naijaledger.sources.health import validate_probe_url
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import list_sources

logger = logging.getLogger("naijaledger.fetch")

# Backward-compatible aliases for tests and callers.
StaticFetchResult = FetchCaptureResult
StaticFetchSummary = FetchBatchSummary


def _response_headers(response: httpx.Response) -> dict[str, str]:
    return {key: value for key, value in response.headers.items()}


def static_fetch_source(
    connection: Connection,
    source: SourceRecord,
    *,
    http_client: httpx.Client,
    minio_client: Minio,
    bucket: str,
    requested_at: datetime | None = None,
) -> FetchCaptureResult:
    if source.fetch_method != "http":
        msg = f"static fetch only supports http sources (got {source.fetch_method})"
        raise ValueError(msg)

    when = requested_at or now_utc()
    url = source.url
    validate_probe_url(url)

    try:
        response = http_client.get(url, follow_redirects=True)
        return persist_fetch_capture(
            connection,
            source,
            url=url,
            requested_at=when,
            status_code=response.status_code,
            body=response.content,
            headers=_response_headers(response),
            error=None,
            minio_client=minio_client,
            bucket=bucket,
        )
    except httpx.HTTPError as exc:
        return persist_fetch_capture(
            connection,
            source,
            url=url,
            requested_at=when,
            status_code=None,
            body=None,
            headers=None,
            error=str(exc),
            minio_client=minio_client,
            bucket=bucket,
        )


def run_static_fetch_for_approved_http_sources(
    connection: Connection,
    *,
    http_client: httpx.Client | None = None,
    minio_client: Minio | None = None,
    bucket: str,
    requested_at: datetime | None = None,
) -> FetchBatchSummary:
    owned_client = http_client is None
    client = http_client or create_http_client()

    summary = empty_batch_summary()
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
            record_batch_result(summary, result)
    finally:
        if owned_client:
            client.close()

    return summary
