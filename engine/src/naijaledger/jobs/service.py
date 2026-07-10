import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row

from naijaledger.jobs.models import EnqueueSummary, Job
from naijaledger.jobs.types import (
    BACKOFF_SECONDS,
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
)
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import list_sources

_JOB_COLUMNS = """
    id, kind, subject_id, status, idempotency_key, run_after, attempts, max_attempts,
    locked_at, locked_by, last_error, result, created_at, updated_at
"""


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _row_to_job(row: Row[Any]) -> Job:
    mapping = row._mapping
    return Job(
        id=mapping["id"],
        kind=mapping["kind"],
        subject_id=mapping["subject_id"],
        status=mapping["status"],
        idempotency_key=mapping["idempotency_key"],
        run_after=mapping["run_after"],
        attempts=mapping["attempts"],
        max_attempts=mapping["max_attempts"],
        locked_at=mapping["locked_at"],
        locked_by=mapping["locked_by"],
        last_error=mapping["last_error"],
        result=mapping["result"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def due_bucket_for_source(source: SourceRecord, *, now: datetime) -> str:
    """Idempotency window: coalesce(last_fetched_at, epoch) + cadence (UTC, second precision)."""
    _ = now
    if source.expected_cadence is None:
        msg = "due_bucket requires expected_cadence"
        raise ValueError(msg)
    base = source.last_fetched_at or datetime(1970, 1, 1, tzinfo=UTC)
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    due_at = base + source.expected_cadence
    return due_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_source_idempotency_key(source: SourceRecord, *, now: datetime) -> str:
    return f"fetch_source:{source.id}:{due_bucket_for_source(source, now=now)}"


def is_source_due(source: SourceRecord, *, now: datetime) -> bool:
    if source.status != "approved":
        return False
    if source.expected_cadence is None:
        return False
    if source.last_fetched_at is None:
        return True
    last = source.last_fetched_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return now >= last + source.expected_cadence


def list_due_sources(connection: Connection, *, now: datetime | None = None) -> list[SourceRecord]:
    when = now or _now_utc()
    return [
        source
        for source in list_sources(connection, status="approved")
        if is_source_due(source, now=when)
    ]


def enqueue_due_fetch_jobs(
    connection: Connection,
    *,
    now: datetime | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> EnqueueSummary:
    when = now or _now_utc()
    attempted = 0
    inserted = 0
    skipped = 0
    insert_query = text(
        f"""
        INSERT INTO jobs (
            kind, subject_id, status, idempotency_key, run_after, max_attempts
        ) VALUES (
            'fetch_source', :subject_id, 'queued', :idempotency_key, :run_after, :max_attempts
        )
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING {_JOB_COLUMNS}
        """
    )
    for source in list_due_sources(connection, now=when):
        attempted += 1
        key = fetch_source_idempotency_key(source, now=when)
        row = connection.execute(
            insert_query,
            {
                "subject_id": source.id,
                "idempotency_key": key,
                "run_after": when,
                "max_attempts": max_attempts,
            },
        ).first()
        if row is None:
            skipped += 1
        else:
            inserted += 1
    return EnqueueSummary(
        attempted=attempted,
        inserted=inserted,
        skipped_conflict=skipped,
    )


def reclaim_stale_jobs(
    connection: Connection,
    *,
    now: datetime | None = None,
    lock_timeout_seconds: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> int:
    when = now or _now_utc()
    cutoff = when - timedelta(seconds=lock_timeout_seconds)
    result = connection.execute(
        text(
            """
            UPDATE jobs
            SET status = 'queued',
                locked_at = NULL,
                locked_by = NULL,
                updated_at = :now
            WHERE status = 'running'
              AND locked_at IS NOT NULL
              AND locked_at < :cutoff
            """
        ),
        {"now": when, "cutoff": cutoff},
    )
    return int(result.rowcount or 0)


def claim_next_job(
    connection: Connection,
    *,
    worker_id: str,
    now: datetime | None = None,
) -> Job | None:
    when = now or _now_utc()
    reclaim_stale_jobs(connection, now=when)
    row = connection.execute(
        text(
            """
            WITH next_job AS (
                SELECT id
                FROM jobs
                WHERE status = 'queued'
                  AND run_after <= :now
                ORDER BY run_after ASC, created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE jobs AS j
            SET status = 'running',
                locked_at = :now,
                locked_by = :worker_id,
                updated_at = :now
            FROM next_job
            WHERE j.id = next_job.id
            RETURNING
                j.id, j.kind, j.subject_id, j.status, j.idempotency_key, j.run_after,
                j.attempts, j.max_attempts, j.locked_at, j.locked_by, j.last_error,
                j.result, j.created_at, j.updated_at
            """
        ),
        {"now": when, "worker_id": worker_id},
    ).first()
    if row is None:
        return None
    return _row_to_job(row)


def get_job(connection: Connection, job_id: UUID) -> Job | None:
    row = connection.execute(
        text(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id = :id"),
        {"id": job_id},
    ).first()
    if row is None:
        return None
    return _row_to_job(row)


def complete_job(
    connection: Connection,
    job_id: UUID,
    *,
    result: dict[str, Any],
    now: datetime | None = None,
) -> Job:
    when = now or _now_utc()
    row = connection.execute(
        text(
            f"""
            UPDATE jobs
            SET status = 'succeeded',
                result = CAST(:result AS jsonb),
                last_error = NULL,
                locked_at = NULL,
                locked_by = NULL,
                updated_at = :now
            WHERE id = :id
            RETURNING {_JOB_COLUMNS}
            """
        ),
        {"id": job_id, "result": json.dumps(result), "now": when},
    ).one()
    return _row_to_job(row)


def fail_job(
    connection: Connection,
    job_id: UUID,
    *,
    error: str,
    now: datetime | None = None,
) -> Job:
    when = now or _now_utc()
    current = get_job(connection, job_id)
    if current is None:
        msg = f"job not found: {job_id}"
        raise LookupError(msg)

    attempts = current.attempts + 1
    if attempts >= current.max_attempts:
        status = "dead"
        run_after = when
    else:
        status = "queued"
        backoff_index = min(attempts - 1, len(BACKOFF_SECONDS) - 1)
        run_after = when + timedelta(seconds=BACKOFF_SECONDS[backoff_index])

    row = connection.execute(
        text(
            f"""
            UPDATE jobs
            SET status = :status,
                attempts = :attempts,
                run_after = :run_after,
                last_error = :error,
                locked_at = NULL,
                locked_by = NULL,
                updated_at = :now
            WHERE id = :id
            RETURNING {_JOB_COLUMNS}
            """
        ),
        {
            "id": job_id,
            "status": status,
            "attempts": attempts,
            "run_after": run_after,
            "error": error[:4000],
            "now": when,
        },
    ).one()
    return _row_to_job(row)
