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
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

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
    licence_field_is_pddl,
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
    awards_skipped: int = 0
    skip_reason: str = ""
    auth_stop: bool = False


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
    """Return response, or a skip/stop reason string."""
    for attempt in range(2):
        try:
            response = _get(hooks, client, url, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == 0:
                hooks.sleep(5)
                continue
            logger.warning("OCP request transport failure url=%s err=%s", url, exc)
            return "fetch_failed"
        if response.status_code in {401, 403}:
            return "stop_auth"
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 0:
                hooks.sleep(5)
                continue
            logger.warning(
                "OCP request retry exhausted url=%s status=%s", url, response.status_code
            )
            return "fetch_failed"
        if response.status_code >= 400:
            logger.warning("OCP request HTTP error url=%s status=%s", url, response.status_code)
            return "fetch_failed"
        return response
    return "fetch_failed"


def _download_body_capped(
    hooks: LoadHooks,
    client: httpx.Client | None,
    url: str,
    *,
    timeout: float,
) -> tuple[httpx.Response, bytes] | str:
    """Fetch download bytes with a compressed-size cap (stream when no test hook)."""
    if hooks.http_get is not None:
        result = _request_with_retry(hooks, client, url, timeout=timeout)
        if isinstance(result, str):
            return result
        body = result.content
        if len(body) > MAX_COMPRESSED_BYTES:
            logger.warning("OCP download exceeded compressed cap url=%s bytes=%s", url, len(body))
            return "fetch_failed"
        return result, body

    assert client is not None
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with client.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
                if response.status_code in {401, 403}:
                    return "stop_auth"
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 0:
                        hooks.sleep(5)
                        continue
                    logger.warning(
                        "OCP download retry exhausted url=%s status=%s",
                        url,
                        response.status_code,
                    )
                    return "fetch_failed"
                if response.status_code >= 400:
                    logger.warning(
                        "OCP download HTTP error url=%s status=%s", url, response.status_code
                    )
                    return "fetch_failed"
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_COMPRESSED_BYTES:
                        logger.warning(
                            "OCP download exceeded compressed cap url=%s bytes=%s", url, total
                        )
                        return "fetch_failed"
                    chunks.append(chunk)
                body = b"".join(chunks)
                frozen = httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    content=body,
                    request=response.request,
                )
                return frozen, body
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            if attempt == 0:
                hooks.sleep(5)
                continue
            logger.warning("OCP download transport failure url=%s err=%s", url, exc)
            return "fetch_failed"
    logger.warning("OCP download failed url=%s err=%s", url, last_error)
    return "fetch_failed"


def _iter_jsonl_gz(body: bytes) -> Iterator[dict[str, Any]]:
    if len(body) > MAX_COMPRESSED_BYTES:
        raise ValueError("compressed_too_large")
    decompressed = 0
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
        while True:
            remaining = MAX_DECOMPRESSED_BYTES - decompressed
            if remaining <= 0:
                raise ValueError("decompressed_too_large")
            line = gz.readline(remaining + 1)
            if not line:
                break
            if len(line) > remaining:
                raise ValueError("line_too_large")
            decompressed += len(line)
            line_text = line.decode("utf-8").strip()
            if not line_text:
                continue
            yield json.loads(line_text)


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
    if not licence_field_is_pddl(record.phrase):
        logger.warning(
            "OCP signed licence record is not PDDL slug=%s phrase=%s",
            publication.slug,
            record.phrase,
        )
        return None, None, "licence_not_pddl"
    expected_page = publication_page_url(publication.publication_id).rstrip("/")
    if record.publication_url.rstrip("/") != expected_page:
        logger.warning(
            "OCP licence record URL mismatch slug=%s record=%s expected=%s",
            publication.slug,
            record.publication_url,
            expected_page,
        )
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
        logger.warning(
            "OCP page missing Last retrieved publication_id=%s", publication.publication_id
        )
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
    status_code: int = 200,
    headers: dict[str, Any] | None = None,
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
        status_code=status_code,
        body=body,
        headers=headers or {"content-type": "application/gzip"},
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
            payload={"release_count": 0, "publication_id": publication.publication_id},
            content_type="application/gzip",
            content_type_conf=1.0,
            status="parsed",
        ),
    )

    failed_releases = 0
    try:
        for raw in _iter_jsonl_gz(body):
            if max_releases is not None and summary.releases >= max_releases:
                break
            try:
                with connection.begin_nested():
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
            except Exception:
                logger.exception(
                    "OCP release load failed publication_id=%s ocid=%s",
                    publication.publication_id,
                    raw.get("ocid") if isinstance(raw, dict) else None,
                )
                failed_releases += 1
                continue
            summary.releases += 1
            summary.awards_written += len(result.award_ids)
            summary.awards_skipped += result.awards_skipped
            # After one-row-per-award-id normalize, award_ids aligns with normalized.awards.
            for award in normalized.awards[: len(result.award_ids)]:
                if award.value_amount is not None and award.value_amount > 0:
                    summary.awards_positive_amount += 1
    except ValueError as exc:
        logger.warning(
            "OCP body parse failed publication_id=%s err=%s releases_ok=%s",
            publication.publication_id,
            exc,
            summary.releases,
        )
        connection.execute(
            text(
                """
                UPDATE extractions
                SET ok = false,
                    status = 'failed',
                    payload = jsonb_set(
                        jsonb_set(
                            COALESCE(payload, '{}'::jsonb),
                            '{release_count}',
                            to_jsonb(CAST(:release_count AS int))
                        ),
                        '{error}',
                        to_jsonb(CAST(:error AS text))
                    )
                WHERE id = :id
                """
            ),
            {"id": extraction.id, "release_count": summary.releases, "error": str(exc)},
        )
        summary.skip_reason = "fetch_failed"
        return summary

    connection.execute(
        text(
            """
            UPDATE extractions
            SET payload = jsonb_set(
                jsonb_set(
                    COALESCE(payload, '{}'::jsonb),
                    '{release_count}',
                    to_jsonb(CAST(:release_count AS int))
                ),
                '{failed_releases}',
                to_jsonb(CAST(:failed_releases AS int))
            )
            WHERE id = :id
            """
        ),
        {"id": extraction.id, "release_count": summary.releases, "failed_releases": failed_releases},
    )

    return summary


def load_one_publication(
    connection: Connection,
    publication: OcpPublication,
    *,
    minio_client: Minio,
    bucket: str,
    licences_dir: Path,
    hooks: LoadHooks,
    client: httpx.Client | None,
    max_releases: int | None = None,
) -> PublicationSummary:
    summary = PublicationSummary(
        state=publication.state_name,
        publication_id=publication.publication_id,
        retrieved_on="",
    )
    _record, retrieved, reason = _gate_publication(
        publication,
        licences_dir=licences_dir,
        hooks=hooks,
        client=client,
    )
    if reason == "stop_auth":
        summary.skip_reason = "fetch_failed"
        summary.auth_stop = True
        logger.error(
            "OCP registry returned 401/403; stopping job publication_id=%s",
            publication.publication_id,
        )
        return summary
    if reason:
        summary.skip_reason = reason
        if reason == "fetch_failed":
            logger.warning(
                "OCP gate fetch_failed publication_id=%s state=%s",
                publication.publication_id,
                publication.state_name,
            )
        return summary
    assert retrieved is not None

    source = find_source_for_publication(connection, publication)
    if source is None or source.status != "approved":
        summary.skip_reason = "fetch_failed"
        logger.warning(
            "OCP publication has no approved source row publication_id=%s status=%s",
            publication.publication_id,
            getattr(source, "status", None),
        )
        return summary

    download_result = _download_body_capped(
        hooks,
        client,
        publication_download_url(publication.publication_id),
        timeout=DOWNLOAD_TIMEOUT_S,
    )
    if download_result == "stop_auth":
        summary.skip_reason = "fetch_failed"
        summary.auth_stop = True
        logger.error(
            "OCP registry returned 401/403 on download; stopping job publication_id=%s",
            publication.publication_id,
        )
        return summary
    if isinstance(download_result, str):
        summary.skip_reason = download_result
        return summary
    response, body = download_result

    return load_publication_body(
        connection,
        source,
        publication,
        body,
        retrieved_on=retrieved,
        minio_client=minio_client,
        bucket=bucket,
        hooks=hooks,
        max_releases=max_releases,
        status_code=response.status_code,
        headers=dict(response.headers),
    )


def _run_publications(
    *,
    open_connection: Callable[[], Any],
    minio_client: Minio,
    bucket: str,
    licences_dir: Path,
    hooks: LoadHooks,
    max_releases: int | None,
    publications: tuple[OcpPublication, ...],
) -> list[PublicationSummary]:
    summaries: list[PublicationSummary] = []
    client: httpx.Client | None = None
    if hooks.http_get is None:
        client = httpx.Client(headers={"User-Agent": USER_AGENT})

    try:
        for index, publication in enumerate(publications):
            if index > 0:
                hooks.sleep(1)
            with open_connection() as connection:
                loaded = load_one_publication(
                    connection,
                    publication,
                    minio_client=minio_client,
                    bucket=bucket,
                    licences_dir=licences_dir,
                    hooks=hooks,
                    client=client,
                    max_releases=max_releases,
                )
                summaries.append(loaded)
            if loaded.auth_stop:
                break
    finally:
        if client is not None:
            client.close()

    return summaries


class _SharedConnection:
    """Context manager that yields an existing connection without closing it."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def __enter__(self) -> Connection:
        return self._connection

    def __exit__(self, *args: object) -> None:
        return None


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
    """Load publications sharing one connection (unit tests)."""
    hooks = hooks or LoadHooks()
    return _run_publications(
        open_connection=lambda: _SharedConnection(connection),
        minio_client=minio_client,
        bucket=bucket,
        licences_dir=licences_dir,
        hooks=hooks,
        max_releases=max_releases,
        publications=publications or PUBLICATIONS,
    )


def run_load_job(
    engine: Engine,
    *,
    minio_client: Minio,
    bucket: str,
    licences_dir: Path,
    hooks: LoadHooks | None = None,
    max_releases: int | None = None,
    publications: tuple[OcpPublication, ...] | None = None,
) -> list[PublicationSummary]:
    """One transaction per publication so a late failure does not roll back earlier states."""
    hooks = hooks or LoadHooks()
    return _run_publications(
        open_connection=engine.begin,
        minio_client=minio_client,
        bucket=bucket,
        licences_dir=licences_dir,
        hooks=hooks,
        max_releases=max_releases,
        publications=publications or PUBLICATIONS,
    )


def format_summary_line(summary: PublicationSummary) -> str:
    return (
        f"{summary.state}\t{summary.publication_id}\t{summary.retrieved_on}\t"
        f"{summary.releases}\t{summary.awards_written}\t"
        f"{summary.awards_positive_amount}\t{summary.skip_reason}"
    )
