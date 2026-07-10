import argparse
import logging
import os
import socket
import time
import uuid

from naijaledger.archive.storage import create_minio_client, ensure_archive_bucket
from naijaledger.config import load_settings
from naijaledger.db.connection import create_db_engine
from naijaledger.jobs.service import enqueue_due_fetch_jobs
from naijaledger.jobs.worker import work_once


def _default_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def _cmd_enqueue() -> None:
    settings = load_settings()
    engine = create_db_engine(settings.database_url)
    with engine.connect() as connection, connection.begin():
        summary = enqueue_due_fetch_jobs(
            connection,
            max_attempts=settings.job_max_attempts,
        )
    print(
        "jobs enqueue:",
        f"attempted={summary['attempted']}",
        f"inserted={summary['inserted']}",
        f"skipped_conflict={summary['skipped_conflict']}",
    )


def _cmd_work(*, once: bool, loop: bool, worker_id: str | None) -> None:
    settings = load_settings()
    minio_client = create_minio_client(settings)
    ensure_archive_bucket(
        minio_client,
        settings.minio_bucket,
        retention_days=settings.minio_retention_days,
    )
    wid = worker_id or _default_worker_id()
    engine = create_db_engine(settings.database_url)

    def _run_one() -> bool:
        with engine.connect() as connection, connection.begin():
            job_id = work_once(
                connection,
                worker_id=wid,
                minio_client=minio_client,
                bucket=settings.minio_bucket,
                settings=settings,
            )
        if job_id is None:
            print(f"jobs work: idle worker_id={wid}")
            return False
        print(f"jobs work: processed job_id={job_id} worker_id={wid}")
        return True

    if once or not loop:
        _run_one()
        return

    while True:
        worked = _run_one()
        if not worked:
            time.sleep(5.0)


def run(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="naijaledger-jobs")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("enqueue", help="Enqueue due fetch_source jobs")

    work = sub.add_parser("work", help="Claim and run jobs")
    work.add_argument("--once", action="store_true", help="Process at most one job")
    work.add_argument("--loop", action="store_true", help="Poll forever")
    work.add_argument("--worker-id", default=None)

    args = parser.parse_args(argv)
    if args.command == "enqueue":
        _cmd_enqueue()
        return
    if args.command == "work":
        _cmd_work(once=args.once, loop=args.loop, worker_id=args.worker_id)
        return
    parser.error(f"unknown command {args.command}")
