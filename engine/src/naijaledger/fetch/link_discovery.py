"""Discover and fetch child artifacts linked from catalog HTML pages."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx
from minio import Minio
from sqlalchemy import text
from sqlalchemy.engine import Connection

from naijaledger.config import Settings, load_settings
from naijaledger.fetch.capture import (
    FetchBatchSummary,
    FetchCaptureResult,
    empty_batch_summary,
    persist_fetch_capture,
    record_batch_result,
)
from naijaledger.sources.health import validate_probe_url
from naijaledger.sources.models import SourceRecord

logger = logging.getLogger("naijaledger.fetch.discovery")

_CHILD_EXTENSIONS: tuple[str, ...] = (".pdf", ".xlsx", ".xls", ".csv", ".json")

CATALOG_SOURCE_URLS: frozenset[str] = frozenset(
    {
        "https://www.lagosppa.gov.ng/registered-awards/",
        "https://dueprocess.jigawastate.gov.ng/contracts",
        "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents",
        "https://neiti.gov.ng/documents/all",
    }
)

BUDGET_OFFICE_INDEX = (
    "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents"
)
_BUDGET_YEAR_PATH = re.compile(
    r"/budget-documents/(?:\d{4}-budget|\d{4}-approved-budget|"
    r"\d{4}-appropriation-amendment-act)/?$",
    re.IGNORECASE,
)


class _HrefExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(value.strip())


def _normalize_host(hostname: str) -> str:
    return hostname.lower().removeprefix("www.")


def is_catalog_source(url: str) -> bool:
    normalized = url.rstrip("/")
    return normalized in {entry.rstrip("/") for entry in CATALOG_SOURCE_URLS}


def is_budget_office_index(url: str) -> bool:
    return url.rstrip("/") == BUDGET_OFFICE_INDEX.rstrip("/")


def is_budget_year_catalog_url(url: str, *, index_url: str = BUDGET_OFFICE_INDEX) -> bool:
    """Year/folder HTML pages under the Budget Office documents index."""
    if not same_origin(index_url, url):
        return False
    path = urlparse(url).path.rstrip("/")
    return _BUDGET_YEAR_PATH.search(path) is not None


def extract_subdir_catalog_links(html: bytes, *, base_url: str) -> list[str]:
    """Discover same-origin nested catalog HTML pages (Budget Office year folders)."""
    parser = _HrefExtractor()
    try:
        parser.feed(html.decode("utf-8", errors="replace"))
    except Exception:
        parser.feed(html.decode("latin-1", errors="replace"))

    seen: set[str] = set()
    discovered: list[str] = []
    for href in parser.hrefs:
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        if not is_budget_year_catalog_url(absolute, index_url=base_url):
            continue
        try:
            validate_probe_url(absolute)
        except ValueError:
            continue
        seen.add(absolute)
        discovered.append(absolute)
    # Prefer recent years first (reverse lexical on YYYY-… paths).
    return sorted(discovered, reverse=True)


def same_origin(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)
    if not base.hostname or not candidate.hostname:
        return False
    return _normalize_host(base.hostname) == _normalize_host(candidate.hostname)


def is_artifact_href(href: str) -> bool:
    stripped = href.strip()
    if not stripped or stripped.startswith(("#", "mailto:", "javascript:", "tel:")):
        return False
    parsed = urlparse(stripped)
    path = parsed.path.lower()
    if any(path.endswith(extension) for extension in _CHILD_EXTENSIONS):
        return True
    if "/viewdocument" in path:
        return True
    if path.endswith("/download") or "/download/" in path:
        return True
    return False


def extract_artifact_links(html: bytes, *, base_url: str) -> list[str]:
    parser = _HrefExtractor()
    try:
        parser.feed(html.decode("utf-8", errors="replace"))
    except Exception:
        parser.feed(html.decode("latin-1", errors="replace"))

    seen: set[str] = set()
    discovered: list[str] = []
    for href in parser.hrefs:
        absolute = urljoin(base_url, href)
        if not is_artifact_href(absolute):
            continue
        if not same_origin(base_url, absolute):
            continue
        try:
            validate_probe_url(absolute)
        except ValueError:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        discovered.append(absolute)
    return discovered


def _title_from_url(url: str) -> str | None:
    path = urlparse(url).path
    filename = path.rsplit("/", 1)[-1]
    if not filename:
        return None
    return re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0]).strip() or None


def has_successful_fetch_for_url(connection: Connection, *, source_id: UUID, url: str) -> bool:
    row = connection.execute(
        text(
            """
            SELECT 1
            FROM fetch_records
            WHERE source_id = :source_id AND url = :url AND ok = true
            LIMIT 1
            """
        ),
        {"source_id": source_id, "url": url},
    ).first()
    return row is not None


def _response_headers(response: httpx.Response) -> dict[str, str]:
    return {key: value for key, value in response.headers.items()}


def fetch_catalog_child(
    connection: Connection,
    source: SourceRecord,
    *,
    child_url: str,
    catalog_url: str,
    parent_document_id: UUID,
    parent_fetch_id: UUID,
    http_client: httpx.Client,
    minio_client: Minio,
    bucket: str,
    requested_at: datetime,
) -> FetchCaptureResult:
    validate_probe_url(child_url)
    discovery_meta: dict[str, Any] = {
        "discovery": {
            "catalog_url": catalog_url,
            "parent_document_id": str(parent_document_id),
            "parent_fetch_id": str(parent_fetch_id),
        }
    }
    try:
        response = http_client.get(child_url, follow_redirects=True)
        return persist_fetch_capture(
            connection,
            source,
            url=child_url,
            requested_at=requested_at,
            status_code=response.status_code,
            body=response.content,
            headers=_response_headers(response),
            error=None,
            minio_client=minio_client,
            bucket=bucket,
            document_meta=discovery_meta,
            document_title=_title_from_url(child_url),
        )
    except httpx.HTTPError as exc:
        return persist_fetch_capture(
            connection,
            source,
            url=child_url,
            requested_at=requested_at,
            status_code=None,
            body=None,
            headers=None,
            error=str(exc),
            minio_client=minio_client,
            bucket=bucket,
        )


def discover_and_fetch_catalog_children(
    connection: Connection,
    source: SourceRecord,
    *,
    catalog_result: FetchCaptureResult,
    catalog_html: bytes,
    catalog_url: str,
    http_client: httpx.Client,
    minio_client: Minio,
    bucket: str,
    requested_at: datetime,
    settings: Settings | None = None,
) -> FetchBatchSummary:
    config = settings or load_settings()
    summary = empty_batch_summary()

    if not catalog_result["ok"]:
        return summary
    if catalog_result["document_id"] is None:
        return summary
    if not is_catalog_source(catalog_url):
        return summary

    parent_document_id = catalog_result["document_id"]
    parent_fetch_id = catalog_result["fetch_record_id"]
    links = extract_artifact_links(catalog_html, base_url=catalog_url)
    # Child URL → (parent_document_id, parent_fetch_id, year_catalog_url)
    pending_year_parents: dict[str, tuple[UUID, UUID, str]] = {}

    # Budget Office index has no direct PDFs — descend into year folders first.
    if is_budget_office_index(catalog_url):
        year_pages = extract_subdir_catalog_links(catalog_html, base_url=catalog_url)
        year_pages = year_pages[: max(0, config.catalog_subdir_max)]
        logger.info(
            "Budget Office: expanding %d year catalog page(s) from %s",
            len(year_pages),
            catalog_url,
        )
        for year_url in year_pages:
            try:
                validate_probe_url(year_url)
                year_response = http_client.get(year_url, follow_redirects=True)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("failed to fetch Budget Office year page %s: %s", year_url, exc)
                continue
            if year_response.status_code >= 400:
                logger.warning(
                    "Budget Office year page %s returned HTTP %s",
                    year_url,
                    year_response.status_code,
                )
                continue

            # Archive year-folder HTML for provenance (skip if already captured ok).
            year_parent_document_id = parent_document_id
            year_parent_fetch_id = parent_fetch_id
            if not has_successful_fetch_for_url(
                connection,
                source_id=source.id,
                url=year_url,
            ):
                year_capture = persist_fetch_capture(
                    connection,
                    source,
                    url=year_url,
                    requested_at=requested_at,
                    status_code=year_response.status_code,
                    body=year_response.content,
                    headers=_response_headers(year_response),
                    error=None,
                    minio_client=minio_client,
                    bucket=bucket,
                    document_meta={
                        "discovery": {
                            "catalog_url": catalog_url,
                            "parent_document_id": str(parent_document_id),
                            "parent_fetch_id": str(parent_fetch_id),
                            "kind": "budget_office_year_page",
                        }
                    },
                    document_title=_title_from_url(year_url),
                )
                record_batch_result(summary, year_capture)
                if year_capture["ok"] and year_capture["document_id"] is not None:
                    year_parent_document_id = year_capture["document_id"]
                    year_parent_fetch_id = year_capture["fetch_record_id"]
            else:
                existing = _latest_ok_fetch_document(
                    connection,
                    source_id=source.id,
                    url=year_url,
                )
                if existing is not None:
                    year_parent_document_id, year_parent_fetch_id = existing

            year_links = extract_artifact_links(year_response.content, base_url=year_url)
            # Prefer binary /download; skip /viewdocument when downloads exist (same doc).
            downloads = [link for link in year_links if "/download" in urlparse(link).path.lower()]
            chosen = downloads if downloads else year_links
            for link in chosen:
                if link not in links:
                    # Stash parent override for this child URL (year page as intermediate).
                    pending_year_parents[link] = (
                        year_parent_document_id,
                        year_parent_fetch_id,
                        year_url,
                    )
                    links.append(link)

    if not links:
        logger.info("no artifact links discovered for catalog %s", catalog_url)
        return summary

    logger.info("discovered %d artifact link(s) from %s", len(links), catalog_url)
    fetched = 0
    for child_url in links:
        if fetched >= config.catalog_discovery_max_children:
            logger.warning(
                "catalog discovery cap reached (%d) for %s",
                config.catalog_discovery_max_children,
                catalog_url,
            )
            break
        if has_successful_fetch_for_url(
            connection,
            source_id=source.id,
            url=child_url,
        ):
            logger.debug("skipping already-fetched child %s", child_url)
            continue
        child_parent_doc = parent_document_id
        child_parent_fetch = parent_fetch_id
        child_catalog_url = catalog_url
        override = pending_year_parents.get(child_url)
        if override is not None:
            child_parent_doc, child_parent_fetch, child_catalog_url = override
        child_result = fetch_catalog_child(
            connection,
            source,
            child_url=child_url,
            catalog_url=child_catalog_url,
            parent_document_id=child_parent_doc,
            parent_fetch_id=child_parent_fetch,
            http_client=http_client,
            minio_client=minio_client,
            bucket=bucket,
            requested_at=requested_at,
        )
        record_batch_result(summary, child_result)
        fetched += 1

    return summary


def _latest_ok_fetch_document(
    connection: Connection,
    *,
    source_id: UUID,
    url: str,
) -> tuple[UUID, UUID] | None:
    row = connection.execute(
        text(
            """
            SELECT d.id AS document_id, fr.id AS fetch_id
            FROM fetch_records fr
            JOIN documents d ON d.sha256 = fr.sha256
            WHERE fr.source_id = :source_id AND fr.url = :url AND fr.ok = true
              AND fr.sha256 IS NOT NULL
            ORDER BY fr.requested_at DESC
            LIMIT 1
            """
        ),
        {"source_id": source_id, "url": url},
    ).first()
    if row is None:
        return None
    return row.document_id, row.fetch_id


def merge_batch_summaries(*summaries: FetchBatchSummary) -> FetchBatchSummary:
    merged = empty_batch_summary()
    for summary in summaries:
        merged["attempted"] += summary["attempted"]
        merged["succeeded"] += summary["succeeded"]
        merged["failed"] += summary["failed"]
    return merged


def absorb_batch_summary(target: FetchBatchSummary, extra: FetchBatchSummary) -> None:
    target["attempted"] += extra["attempted"]
    target["succeeded"] += extra["succeeded"]
    target["failed"] += extra["failed"]
