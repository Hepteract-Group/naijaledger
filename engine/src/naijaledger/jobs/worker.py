from collections.abc import Callable
from typing import Any
from uuid import UUID

from minio import Minio
from sqlalchemy.engine import Connection

from naijaledger.config import Settings, load_settings
from naijaledger.documents.service import get_document
from naijaledger.fetch.capture import FetchCaptureResult
from naijaledger.fetch.playwright_fetch import playwright_fetch_source
from naijaledger.fetch.scrapling_fetch import scrapling_fetch_source
from naijaledger.fetch.static import static_fetch_source
from naijaledger.finance.adapters import adapter_for_source
from naijaledger.finance.normalize_load import run_normalize_load_for_document
from naijaledger.http.client import create_http_client
from naijaledger.jobs.models import Job
from naijaledger.jobs.service import (
    complete_job,
    enqueue_normalize_load_job,
    fail_job,
    get_job,
)
from naijaledger.sources.service import get_source

FetchSourceFn = Callable[..., FetchCaptureResult]


def _maybe_enqueue_normalize_load(
    connection: Connection,
    *,
    document_id: UUID,
    settings: Settings,
) -> str | None:
    document = get_document(connection, document_id)
    source = get_source(connection, document.source_id)
    adapter = adapter_for_source(source_url=source.url, document_format=document.format)
    if adapter is None:
        return None
    job = enqueue_normalize_load_job(
        connection,
        document_id=document_id,
        adapter_id=adapter.adapter_id,
        method_version=adapter.method_version,
        max_attempts=settings.job_max_attempts,
    )
    return str(job.id) if job is not None else "already_queued"


def run_fetch_source_job(
    connection: Connection,
    job: Job,
    *,
    minio_client: Minio,
    bucket: str,
    settings: Settings | None = None,
    fetch_fn: FetchSourceFn | None = None,
) -> dict[str, Any]:
    """Dispatch a fetch_source job to the existing per-method fetch helpers."""
    if job.kind != "fetch_source":
        msg = f"unsupported job kind: {job.kind}"
        raise ValueError(msg)

    source = get_source(connection, job.subject_id)
    cfg = settings or load_settings()

    if fetch_fn is not None:
        result = fetch_fn(
            connection,
            source,
            minio_client=minio_client,
            bucket=bucket,
            settings=cfg,
        )
    elif source.fetch_method == "http":
        with create_http_client() as http_client:
            result = static_fetch_source(
                connection,
                source,
                http_client=http_client,
                minio_client=minio_client,
                bucket=bucket,
            )
    elif source.fetch_method == "scrapling":
        with create_http_client() as http_client:
            result = scrapling_fetch_source(
                connection,
                source,
                minio_client=minio_client,
                bucket=bucket,
                settings=cfg,
                http_client=http_client,
            )
    elif source.fetch_method == "playwright":
        result = playwright_fetch_source(
            connection,
            source,
            minio_client=minio_client,
            bucket=bucket,
            settings=cfg,
        )
    else:
        msg = f"unsupported fetch_method: {source.fetch_method}"
        raise ValueError(msg)

    summary: dict[str, Any] = {
        "fetch_record_id": str(result["fetch_record_id"]),
        "ok": result["ok"],
        "archive_key": result["archive_key"],
        "document_id": str(result["document_id"]) if result["document_id"] else None,
        "normalize_load_job_id": None,
    }
    if not result["ok"]:
        msg = f"fetch did not succeed for source {source.id}"
        raise RuntimeError(msg)
    if result["document_id"] is not None:
        summary["normalize_load_job_id"] = _maybe_enqueue_normalize_load(
            connection,
            document_id=result["document_id"],
            settings=cfg,
        )
    return summary


def run_normalize_load_job(
    connection: Connection,
    job: Job,
    *,
    minio_client: Minio,
    bucket: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    if job.kind != "normalize_load":
        msg = f"unsupported job kind: {job.kind}"
        raise ValueError(msg)
    cfg = settings or load_settings()
    return run_normalize_load_for_document(
        connection,
        job.subject_id,
        minio_client=minio_client,
        bucket=bucket,
        settings=cfg,
    )


def process_claimed_job(
    connection: Connection,
    job: Job,
    *,
    minio_client: Minio,
    bucket: str,
    settings: Settings | None = None,
    fetch_fn: FetchSourceFn | None = None,
) -> Job:
    try:
        if job.kind == "fetch_source":
            result = run_fetch_source_job(
                connection,
                job,
                minio_client=minio_client,
                bucket=bucket,
                settings=settings,
                fetch_fn=fetch_fn,
            )
        elif job.kind == "normalize_load":
            result = run_normalize_load_job(
                connection,
                job,
                minio_client=minio_client,
                bucket=bucket,
                settings=settings,
            )
        else:
            msg = f"unsupported job kind: {job.kind}"
            raise ValueError(msg)
        return complete_job(connection, job.id, result=result)
    except Exception as exc:  # noqa: BLE001 — job boundary must record any failure
        return fail_job(connection, job.id, error=str(exc))


def work_once(
    connection: Connection,
    *,
    worker_id: str,
    minio_client: Minio,
    bucket: str,
    settings: Settings | None = None,
    fetch_fn: FetchSourceFn | None = None,
) -> UUID | None:
    from naijaledger.jobs.service import claim_next_job

    job = claim_next_job(connection, worker_id=worker_id)
    if job is None:
        return None
    finished = process_claimed_job(
        connection,
        job,
        minio_client=minio_client,
        bucket=bucket,
        settings=settings,
        fetch_fn=fetch_fn,
    )
    return finished.id


def ensure_job(connection: Connection, job_id: UUID) -> Job:
    job = get_job(connection, job_id)
    if job is None:
        msg = f"job not found: {job_id}"
        raise LookupError(msg)
    return job
