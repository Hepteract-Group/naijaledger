from datetime import datetime
from typing import Any, TypedDict, cast

from minio import Minio
from sqlalchemy.engine import Connection

from naijaledger.config import Settings, load_settings
from naijaledger.fetch.capture import (
    FetchBatchSummary,
    FetchCaptureResult,
    empty_batch_summary,
    now_utc,
    persist_fetch_capture,
    record_batch_result,
)
from naijaledger.sources.health import validate_probe_url
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import list_sources


class ScraplingPageResult(TypedDict):
    status_code: int | None
    body: bytes | None
    headers: dict[str, str] | None
    error: str | None


def _normalize_headers(raw: object) -> dict[str, str]:
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        return {str(key): str(value) for key, value in raw}
    return {}


def fetch_url_with_scrapling(url: str, *, settings: Settings | None = None) -> ScraplingPageResult:
    config = settings or load_settings()
    validate_probe_url(url)

    try:
        from scrapling.fetchers import Fetcher
    except ModuleNotFoundError as exc:
        msg = "scrapling fetchers not installed; add scrapling[fetchers] dependency"
        raise RuntimeError(msg) from exc

    try:
        page = Fetcher.get(
            url,
            stealthy_headers=config.scrapling_stealthy_headers,
            impersonate=cast(Any, config.scrapling_impersonate),
            timeout=config.scrapling_timeout,
            follow_redirects=True,
        )
    except Exception as exc:
        return ScraplingPageResult(
            status_code=None,
            body=None,
            headers=None,
            error=str(exc),
        )

    body = page.body if page.body else None
    if body is None and page.text:
        body = page.text.encode(page.encoding or "utf-8")

    return ScraplingPageResult(
        status_code=page.status,
        body=body,
        headers=_normalize_headers(page.headers),
        error=None,
    )


def scrapling_fetch_source(
    connection: Connection,
    source: SourceRecord,
    *,
    minio_client: Minio,
    bucket: str,
    requested_at: datetime | None = None,
    settings: Settings | None = None,
) -> FetchCaptureResult:
    if source.fetch_method != "scrapling":
        msg = f"scrapling fetch only supports scrapling sources (got {source.fetch_method})"
        raise ValueError(msg)

    when = requested_at or now_utc()
    page = fetch_url_with_scrapling(source.url, settings=settings)
    return persist_fetch_capture(
        connection,
        source,
        url=source.url,
        requested_at=when,
        status_code=page["status_code"],
        body=page["body"],
        headers=page["headers"],
        error=page["error"],
        minio_client=minio_client,
        bucket=bucket,
    )


def run_scrapling_fetch_for_approved_scrapling_sources(
    connection: Connection,
    *,
    minio_client: Minio | None = None,
    bucket: str,
    requested_at: datetime | None = None,
    settings: Settings | None = None,
) -> FetchBatchSummary:
    if minio_client is None:
        msg = "minio_client is required"
        raise ValueError(msg)

    summary = empty_batch_summary()
    sources = [
        source
        for source in list_sources(connection, status="approved")
        if source.fetch_method == "scrapling"
    ]

    for source in sources:
        result = scrapling_fetch_source(
            connection,
            source,
            minio_client=minio_client,
            bucket=bucket,
            requested_at=requested_at,
            settings=settings,
        )
        record_batch_result(summary, result)

    return summary
