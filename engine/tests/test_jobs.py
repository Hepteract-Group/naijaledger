from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy import text

from naijaledger.fetch.capture import FetchCaptureResult
from naijaledger.jobs.service import (
    claim_next_job,
    complete_job,
    enqueue_due_fetch_jobs,
    fail_job,
    get_job,
    is_source_due,
    list_due_sources,
    reclaim_stale_jobs,
)
from naijaledger.jobs.worker import process_claimed_job, work_once
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source, record_fetch_success


def _approved_source(db_connection, *, cadence_days: int = 7, name: str = "Jobs Source"):
    source = create_source(
        db_connection,
        SourceCreate(
            name=name,
            jurisdiction="federal",
            category="procurement",
            url=f"https://example.com/{uuid4().hex}",
            fetch_method="http",
            format="html",
            expected_cadence=timedelta(days=cadence_days),
            added_by=SEED_ADDED_BY,
        ),
    )
    return approve_source(db_connection, source.id, approved_by="test")


def test_jobs_table_exists(db_connection) -> None:
    rows = db_connection.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'jobs'
            """
        )
    ).all()
    columns = {row[0] for row in rows}
    assert "idempotency_key" in columns
    assert "status" in columns


def test_list_due_sources_rules(db_connection) -> None:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    due = _approved_source(db_connection, name="Due Never Fetched")
    fresh = _approved_source(db_connection, name="Fresh")
    record_fetch_success(
        db_connection,
        fresh.id,
        fetched_at=now - timedelta(hours=1),
        content_hash="abc",
    )
    no_cadence = create_source(
        db_connection,
        SourceCreate(
            name="No Cadence",
            jurisdiction="federal",
            category="budget",
            url=f"https://example.com/{uuid4().hex}",
            fetch_method="http",
            format="html",
            expected_cadence=None,
            added_by=SEED_ADDED_BY,
        ),
    )
    approve_source(db_connection, no_cadence.id, approved_by="test")

    due_ids = {source.id for source in list_due_sources(db_connection, now=now)}
    assert due.id in due_ids
    assert fresh.id not in due_ids
    assert no_cadence.id not in due_ids
    assert is_source_due(due, now=now) is True


def test_enqueue_idempotent(db_connection) -> None:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    _approved_source(db_connection, name="Enqueue Once")
    first = enqueue_due_fetch_jobs(db_connection, now=now)
    second = enqueue_due_fetch_jobs(db_connection, now=now)
    assert first["inserted"] >= 1
    assert second["inserted"] == 0
    assert second["skipped_conflict"] >= 1


def test_claim_and_complete(db_connection) -> None:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    _approved_source(db_connection, name="Claim Complete")
    enqueue_due_fetch_jobs(db_connection, now=now)
    job = claim_next_job(db_connection, worker_id="worker-a", now=now)
    assert job is not None
    assert job.status == "running"
    assert job.locked_by == "worker-a"
    done = complete_job(
        db_connection,
        job.id,
        result={"fetch_record_id": str(uuid4()), "ok": True},
        now=now,
    )
    assert done.status == "succeeded"
    assert done.result is not None
    assert done.result["ok"] is True


def test_fail_retries_then_dead(db_connection) -> None:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    _approved_source(db_connection, name="Fail Retry")
    enqueue_due_fetch_jobs(db_connection, now=now, max_attempts=2)
    job = claim_next_job(db_connection, worker_id="w1", now=now)
    assert job is not None
    failed = fail_job(db_connection, job.id, error="boom", now=now)
    assert failed.status == "queued"
    assert failed.attempts == 1
    assert failed.run_after > now

    again = claim_next_job(
        db_connection,
        worker_id="w1",
        now=failed.run_after,
    )
    assert again is not None
    dead = fail_job(db_connection, again.id, error="boom2", now=failed.run_after)
    assert dead.status == "dead"
    assert dead.attempts == 2


def test_reclaim_stale_running(db_connection) -> None:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    _approved_source(db_connection, name="Stale Lock")
    enqueue_due_fetch_jobs(db_connection, now=now)
    job = claim_next_job(db_connection, worker_id="w-stale", now=now)
    assert job is not None
    # Backdate lock
    db_connection.execute(
        text("UPDATE jobs SET locked_at = :old WHERE id = :id"),
        {"old": now - timedelta(hours=2), "id": job.id},
    )
    reclaimed = reclaim_stale_jobs(
        db_connection,
        now=now,
        lock_timeout_seconds=1800,
    )
    assert reclaimed == 1
    refreshed = get_job(db_connection, job.id)
    assert refreshed is not None
    assert refreshed.status == "queued"


def test_work_once_with_mock_fetch(db_connection) -> None:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    source = _approved_source(db_connection, name="Work Once")
    enqueue_due_fetch_jobs(db_connection, now=now)
    fetch_id = uuid4()

    def fake_fetch(_connection, _source, **_kwargs) -> FetchCaptureResult:
        return FetchCaptureResult(
            fetch_record_id=fetch_id,
            ok=True,
            archive_key="sha256/abc",
            content_hash="abc",
            document_id=None,
        )

    minio = MagicMock()
    job_id = work_once(
        db_connection,
        worker_id="worker-mock",
        minio_client=minio,
        bucket="test",
        fetch_fn=fake_fetch,
    )
    assert job_id is not None
    job = get_job(db_connection, job_id)
    assert job is not None
    assert job.status == "succeeded"
    assert job.result is not None
    assert job.result["fetch_record_id"] == str(fetch_id)
    assert job.subject_id == source.id


def test_process_claimed_job_records_failure(db_connection) -> None:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    _approved_source(db_connection, name="Work Fail")
    enqueue_due_fetch_jobs(db_connection, now=now, max_attempts=3)
    job = claim_next_job(db_connection, worker_id="w-fail", now=now)
    assert job is not None

    def boom(*_args, **_kwargs) -> FetchCaptureResult:
        raise RuntimeError("network down")

    finished = process_claimed_job(
        db_connection,
        job,
        minio_client=MagicMock(),
        bucket="test",
        fetch_fn=boom,
    )
    assert finished.status == "queued"
    assert finished.attempts == 1
    assert finished.last_error is not None
    assert "network down" in finished.last_error


def test_fetch_success_enqueues_normalize_load_for_ekiti(db_connection) -> None:
    from naijaledger.finance.adapters import EKITI_URL

    now = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
    source = create_source(
        db_connection,
        SourceCreate(
            name="Ekiti Jobs",
            jurisdiction="state",
            region="Ekiti",
            category="procurement",
            url=EKITI_URL,
            fetch_method="scrapling",
            format="html",
            expected_cadence=timedelta(days=7),
            added_by=SEED_ADDED_BY,
        ),
    )
    approve_source(db_connection, source.id, approved_by="test")
    enqueue_due_fetch_jobs(db_connection, now=now)

    fetch_row_id = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, 'ekiti-job-hash', 'sha256/ekiti-job-hash'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "url": source.url},
    ).scalar_one()
    doc_id = db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key, title
            ) VALUES (
                :source_id, :fetch_id, 'ekiti-job-hash', 'html',
                'sha256/ekiti-job-hash', 'Ekiti'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "fetch_id": fetch_row_id},
    ).scalar_one()

    def fake_fetch(_connection, _source, **_kwargs) -> FetchCaptureResult:
        return FetchCaptureResult(
            fetch_record_id=fetch_row_id,
            ok=True,
            archive_key="sha256/ekiti-job-hash",
            content_hash="ekiti-job-hash",
            document_id=doc_id,
        )

    job_id = work_once(
        db_connection,
        worker_id="worker-ekiti",
        minio_client=MagicMock(),
        bucket="test",
        fetch_fn=fake_fetch,
    )
    assert job_id is not None
    fetch_job = get_job(db_connection, job_id)
    assert fetch_job is not None
    assert fetch_job.result is not None
    assert fetch_job.result["normalize_load_job_id"] is not None

    normalize_job = claim_next_job(db_connection, worker_id="worker-norm")
    assert normalize_job is not None
    assert normalize_job.kind == "normalize_load"
    assert normalize_job.subject_id == doc_id


def test_normalize_load_job_loads_fixture(db_connection) -> None:
    from pathlib import Path

    from naijaledger.finance.adapters import EKITI_URL
    from naijaledger.jobs.service import enqueue_normalize_load_job

    source = create_source(
        db_connection,
        SourceCreate(
            name="Ekiti Normalize",
            jurisdiction="state",
            region="Ekiti",
            category="procurement",
            url=EKITI_URL,
            fetch_method="scrapling",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    fetch_row = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, 'ekiti-nl', 'sha256/ekiti-nl'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "url": source.url},
    ).scalar_one()
    doc_id = db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key, title
            ) VALUES (
                :source_id, :fetch_id, 'ekiti-nl', 'html', 'sha256/ekiti-nl', 'Ekiti'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "fetch_id": fetch_row},
    ).scalar_one()

    job = enqueue_normalize_load_job(
        db_connection,
        document_id=doc_id,
        adapter_id="ekiti-html-table",
        method_version="ekiti-html-table-2",
    )
    assert job is not None
    claimed = claim_next_job(db_connection, worker_id="nl-worker")
    assert claimed is not None

    html = (Path(__file__).parent / "fixtures" / "ekiti_procurements.html").read_bytes()
    minio = MagicMock()
    response = MagicMock()
    response.read.return_value = html
    minio.get_object.return_value = response

    finished = process_claimed_job(
        db_connection,
        claimed,
        minio_client=minio,
        bucket="test",
    )
    assert finished.status == "succeeded"
    assert finished.result is not None
    assert finished.result["skipped"] is False
    assert finished.result["release_count"] == 2
    assert db_connection.execute(text("SELECT count(*) FROM tenders")).scalar_one() >= 2


def test_normalize_load_skips_when_no_adapter(db_connection) -> None:
    from naijaledger.jobs.service import enqueue_normalize_load_job

    source = create_source(
        db_connection,
        SourceCreate(
            name="No Adapter Source",
            jurisdiction="federal",
            category="other",
            url=f"https://example.com/{uuid4().hex}",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    fetch_row = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, 'no-adapter', 'sha256/no-adapter'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "url": source.url},
    ).scalar_one()
    doc_id = db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key, title
            ) VALUES (
                :source_id, :fetch_id, 'no-adapter', 'html', 'sha256/no-adapter', 'x'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "fetch_id": fetch_row},
    ).scalar_one()

    # Force a normalize_load job even though no adapter matches (backfill / misconfig).
    job = enqueue_normalize_load_job(
        db_connection,
        document_id=doc_id,
        adapter_id="none",
        method_version="none-1",
    )
    assert job is not None
    claimed = claim_next_job(db_connection, worker_id="skip-worker")
    assert claimed is not None
    finished = process_claimed_job(
        db_connection,
        claimed,
        minio_client=MagicMock(),
        bucket="test",
    )
    assert finished.status == "succeeded"
    assert finished.result is not None
    assert finished.result["skipped"] is True
    assert finished.result["reason"] == "no_adapter"
