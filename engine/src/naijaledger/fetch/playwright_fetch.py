"""Playwright-backed fetch via Scrapling DynamicFetcher (E3.3b)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypedDict, cast
from urllib.parse import urlparse

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


class PlaywrightPageResult(TypedDict):
    status_code: int | None
    body: bytes | None
    headers: dict[str, str] | None
    error: str | None


class _PlaywrightLocator(Protocol):
    def count(self) -> int: ...

    @property
    def first(self) -> _PlaywrightLocator: ...

    def click(self) -> None: ...


class _PlaywrightPage(Protocol):
    def locator(self, selector: str) -> _PlaywrightLocator: ...


def _normalize_headers(raw: object) -> dict[str, str]:
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        return {str(key): str(value) for key, value in raw}
    return {}


def dismiss_nocopo_license_modal(page: _PlaywrightPage) -> None:
    """Close the static NOCOPO license notice so the Open-Data table can render."""
    for selector in (
        "#adroitAlert button[data-bs-dismiss='modal']",
        "#adroitAlert .btn-close",
    ):
        locator = page.locator(selector)
        if locator.count() > 0:
            locator.first.click()
            return


def playwright_fetch_options(url: str, *, settings: Settings) -> dict[str, Any]:
    options: dict[str, Any] = {
        "headless": settings.playwright_headless,
        "network_idle": settings.playwright_network_idle,
        "load_dom": True,
        "timeout": int(settings.playwright_timeout * 1000),
        "wait": settings.playwright_post_wait_ms,
        "disable_resources": True,
    }
    host = urlparse(url).netloc.lower()
    if "nocopo.bpp.gov.ng" in host:
        options["page_action"] = dismiss_nocopo_license_modal
    if "dueprocess.gm.gov.ng" in host:
        options["wait"] = max(int(options["wait"]), 3000)
    return options


def fetch_url_with_playwright(
    url: str,
    *,
    settings: Settings | None = None,
) -> PlaywrightPageResult:
    config = settings or load_settings()
    validate_probe_url(url)

    try:
        from scrapling.fetchers import DynamicFetcher
    except ModuleNotFoundError as exc:
        msg = "scrapling fetchers not installed; add scrapling[fetchers] dependency"
        raise RuntimeError(msg) from exc

    options = playwright_fetch_options(url, settings=config)
    try:
        page = DynamicFetcher.fetch(url, **cast(Any, options))
    except Exception as exc:
        return PlaywrightPageResult(
            status_code=None,
            body=None,
            headers=None,
            error=str(exc),
        )

    body = page.body if page.body else None
    if body is None and page.text:
        body = page.text.encode(page.encoding or "utf-8")

    return PlaywrightPageResult(
        status_code=page.status,
        body=body,
        headers=_normalize_headers(page.headers),
        error=None,
    )


def playwright_fetch_source(
    connection: Connection,
    source: SourceRecord,
    *,
    minio_client: Minio,
    bucket: str,
    requested_at: datetime | None = None,
    settings: Settings | None = None,
) -> FetchCaptureResult:
    if source.fetch_method != "playwright":
        msg = f"playwright fetch only supports playwright sources (got {source.fetch_method})"
        raise ValueError(msg)

    when = requested_at or now_utc()
    page = fetch_url_with_playwright(source.url, settings=settings)
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


def run_playwright_fetch_for_approved_playwright_sources(
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
        if source.fetch_method == "playwright"
    ]

    for source in sources:
        result = playwright_fetch_source(
            connection,
            source,
            minio_client=minio_client,
            bucket=bucket,
            requested_at=requested_at,
            settings=settings,
        )
        record_batch_result(summary, result)

    return summary
