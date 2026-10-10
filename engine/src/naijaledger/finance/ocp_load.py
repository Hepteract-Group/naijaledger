"""Load OCP Data Registry state bulk JSONL.gz files (spec 0041 / #203)."""

from __future__ import annotations

import gzip
import io
import json
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from minio import Minio
from sqlalchemy.engine import Connection

from naijaledger.extractions.models import ExtractionCreate
from naijaledger.extractions.service import create_extraction
from naijaledger.fetch.capture import now_utc, persist_fetch_capture
from naijaledger.finance.ocds import normalize_ocds_release
from naijaledger.finance.ocds_load import load_normalized_release
from naijaledger.finance.ocds_models import ProvenanceContext
from naijaledger.finance.ocp_registry import (
    DOWNLOAD_TIMEOUT_S,
    MAX_COMPRESSED_BYTES,
    MAX_DECOMPRESSED_BYTES,
    PAGE_TIMEOUT_S,
    PUBLICATIONS,
    USER_AGENT,
    LicenceRecord,
    OcpPublication,
    licence_matches_record,
    load_licence_record,
    parse_last_retrieved,
    parse_licence_field,
    prepare_release_dict,
    publication_download_url,
    publication_page_url,
    stamp_normalized_release,
)
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import list_sources

logger = logging.getLogger("naijaledger.finance.ocp_load")

HttpGet = Callable[..., httpx.Response]
ArchiveHook = Callable[[str, bytes], None]


@dataclass
class PublicationSummary:
    state: str
    publication_id: str
    retrieved_on: str
    releases: int = 0
    awards_written: int = 0
    awards_positive_amount: int = 0
    skip_reason: str = ""


@dataclass
class LoadHooks:
    """Test seams: override HTTP and observe archive-before-parse order."""

    http_get: HttpGet | None = None
    on_archived: ArchiveHook | None = None
    sleep: Callable[[float], None] = time.sleep
    events: list[str] = field(default_factory=list)


def find_source_for_publication(
    connection: Connection,
    publication: OcpPublication,
) -> SourceRecord | None:
    download = publication_download_url(publication.publication_id)
    page = publication_page_url(publication.publication_id)
    for source in list_sources(connection):
        if source.url.rstrip("/") in {download.rstrip("/"), page.rstrip("/")}:
            return source
    return None


def _get(
    hooks: LoadHooks,
    client: httpx.Client | None,
    url: str,
    *,
    timeout: float,
) -> httpx.Response:
    if hooks.http_get is not None:
        return hooks.http_get(url, timeout=timeout)
    assert client is not None
    return client.get(url, timeout=timeout, follow_redirects=True)


def _request_with_retry(
    hooks: LoadHooks,
    client: httpx.Client | None,
    url: str,
    *,
    timeout: float,
) -> httpx.Response | str:
    """Return response or skip_reason / raise SystemExit-style stop token."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = _get(hooks, client, url, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            if attempt == 0:
                hooks.sleep(5)
                continue
            return "fetch_failed"
        if response.status_code in {401, 403}:
            return "stop_auth"
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 0:
                hooks.sleep(5)
                continue
            return "fetch_failed"
        if response.status_code >= 400:
            return "fetch_failed"
        return response
    return "fetch_failed" if last_error is not None else "fetch_failed"


def _iter_jsonl_gz(body: bytes) -> Iterator[dict[str, Any]]:
    if len(body) > MAX_COMPRESSED_BYTES:
        raise ValueError("compressed_too_large")
    decompressed = 0
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
        while True:
            line = gz.readline()
            if not line:
                break
            decompressed += len(line)
            if decompressed > MAX_DECOMPRESSED_BYTES:
                raise ValueError("decompressed_too_large")
            text = line.decode("utf-8").strip()
            if not text:
                continue
            yield json.loads(text)


def _gate_publication(
    publication: OcpPublication,
    *,
    licences_dir: Path,
    hooks: LoadHooks,
    client: httpx.Client | None,
) -> tuple[LicenceRecord | None, date | None, str]:
    record = load_licence_record(licences_dir, publication.slug)
    if record is None:
        return None, None, "no_licence_record"

    page_result = _request_with_retry(
        hooks,
        client,
        publication_page_url(publication.publication_id),
        timeout=PAGE_TIMEOUT_S,
    )
    if page_result == "stop_auth":
        return None, None, "stop_auth"
    if isinstance(page_result, str):
        return None, None, page_result

    field = parse_licence_field(page_result.text)
    if field is None or not field.strip():
        return None, None, "no_open_licence"
    if not licence_matches_record(field, record):
        return None, None, "licence_mismatch"

    retrieved = parse_last_retrieved(page_result.text)
    if retrieved is None:
        return None, None, "fetch_failed"
    return record, retrieved, ""


def load_publication_body(
    connection: Connection,
    source: SourceRecord,
    publication: OcpPublication,
    body: bytes,
    *,
    retrieved_on: date,
    minio_client: Minio,
    bucket: str,
    hooks: LoadHooks | None = None,
    max_releases: int | None = None,
) -> PublicationSummary:
    hooks = hooks or LoadHooks()
    summary = PublicationSummary(
        state=publication.state_name,
        publication_id=publication.publication_id,
        retrieved_on=retrieved_on.isoformat(),
    )
    download_url = publication_download_url(publication.publication_id)
    hooks.events.append("archive_start")
    if hooks.on_archived is not None:
        hooks.on_archived(download_url, body)
    capture = persist_fetch_capture(
        connection,
        source,
        url=download_url,
        requested_at=now_utc(),
        status_code=200,
        body=body,
        headers={"content-type": "application/gzip"},
        error=None,
        minio_client=minio_client,
        bucket=bucket,
        document_title=f"OCP {publication.state_name} full.jsonl.gz",
        document_meta={
            "ocp_publication_id": publication.publication_id,
            "ocp_retrieved_on": retrieved_on.isoformat(),
        },
    )
    hooks.events.append("archive_done")
    if not capture["ok"] or capture["document_id"] is None:
        summary.skip_reason = "fetch_failed"
        return summary

    document_id = capture["document_id"]
    try:
        releases = list(_iter_jsonl_gz(body))
    except ValueError:
        summary.skip_reason = "fetch_failed"
        return summary

    if max_releases is not None:
        releases = releases[:max_releases]

    hooks.events.append("parse_start")
    extraction = create_extraction(
        connection,
        ExtractionCreate(
            document_id=document_id,
            method="json",
            method_version="ocp-registry-bulk-1",
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload={"release_count": len(releases), "publication_id": publication.publication_id},
            content_type="application/gzip",
            content_type_conf=1.0,
            status="parsed",
        ),
    )

    for raw in releases:
        prepared = prepare_release_dict(raw)
        normalized = normalize_ocds_release(prepared)
        stamp_normalized_release(
            normalized,
            state_code=publication.state_code,
            publication_id=publication.publication_id,
            retrieved_on=retrieved_on,
        )
        provenance = ProvenanceContext(
            document_id=document_id,
            extraction_id=extraction.id,
            method="json",
            derivation="extracted",
            confidence=1.0,
            region={
                "ocid": normalized.ocid,
                "publication_id": publication.publication_id,
            },
        )
        result = load_normalized_release(connection, normalized, provenance=provenance)
        summary.releases += 1
        summary.awards_written += len(result.award_ids)
        for award in normalized.awards:
            if award.value_amount is not None and award.value_amount > 0:
                summary.awards_positive_amount += 1

    return summary


def load_all_publications(
    connection: Connection,
    *,
    minio_client: Minio,
    bucket: str,
    licences_dir: Path,
    hooks: LoadHooks | None = None,
    max_releases: int | None = None,
    publications: tuple[OcpPublication, ...] | None = None,
) -> list[PublicationSummary]:
    hooks = hooks or LoadHooks()
    pubs = publications or PUBLICATIONS
    summaries: list[PublicationSummary] = []
    client: httpx.Client | None = None
    if hooks.http_get is None:
        client = httpx.Client(headers={"User-Agent": USER_AGENT})

    try:
        for index, publication in enumerate(pubs):
            if index > 0:
                hooks.sleep(1)
            summary = PublicationSummary(
                state=publication.state_name,
                publication_id=publication.publication_id,
                retrieved_on="",
            )
            record, retrieved, reason = _gate_publication(
                publication,
                licences_dir=licences_dir,
                hooks=hooks,
                client=client,
            )
            if reason == "stop_auth":
                summary.skip_reason = "fetch_failed"
                summaries.append(summary)
                logger.error("OCP registry returned 401/403; stopping job")
                break
            if reason:
                summary.skip_reason = reason
                summaries.append(summary)
                continue
            assert record is not None and retrieved is not None

            source = find_source_for_publication(connection, publication)
            if source is None or source.status != "approved":
                summary.skip_reason = "fetch_failed"
                summaries.append(summary)
                continue

            download_result = _request_with_retry(
                hooks,
                client,
                publication_download_url(publication.publication_id),
                timeout=DOWNLOAD_TIMEOUT_S,
            )
            if download_result == "stop_auth":
                summary.skip_reason = "fetch_failed"
                summaries.append(summary)
                break
            if isinstance(download_result, str):
                summary.skip_reason = download_result
                summaries.append(summary)
                continue
            body = download_result.content
            if len(body) > MAX_COMPRESSED_BYTES:
                summary.skip_reason = "fetch_failed"
                summaries.append(summary)
                continue

            loaded = load_publication_body(
                connection,
                source,
                publication,
                body,
                retrieved_on=retrieved,
                minio_client=minio_client,
                bucket=bucket,
                hooks=hooks,
                max_releases=max_releases,
            )
            summaries.append(loaded)
    finally:
        if client is not None:
            client.close()

    return summaries


def format_summary_line(summary: PublicationSummary) -> str:
    return (
        f"{summary.state}\t{summary.publication_id}\t{summary.retrieved_on}\t"
        f"{summary.releases}\t{summary.awards_written}\t"
        f"{summary.awards_positive_amount}\t{summary.skip_reason}"
    )
