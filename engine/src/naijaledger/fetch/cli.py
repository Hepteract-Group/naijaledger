import logging

from naijaledger.archive.storage import create_minio_client, ensure_archive_bucket
from naijaledger.config import load_settings
from naijaledger.db.connection import create_db_engine
from naijaledger.fetch.playwright_fetch import run_playwright_fetch_for_approved_playwright_sources
from naijaledger.fetch.scrapling_fetch import run_scrapling_fetch_for_approved_scrapling_sources
from naijaledger.fetch.static import run_static_fetch_for_approved_http_sources


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    minio_client = create_minio_client(settings)
    ensure_archive_bucket(
        minio_client,
        settings.minio_bucket,
        retention_days=settings.minio_retention_days,
    )

    engine = create_db_engine()
    with engine.connect() as connection, connection.begin():
        http_summary = run_static_fetch_for_approved_http_sources(
            connection,
            minio_client=minio_client,
            bucket=settings.minio_bucket,
        )
        scrapling_summary = run_scrapling_fetch_for_approved_scrapling_sources(
            connection,
            minio_client=minio_client,
            bucket=settings.minio_bucket,
            settings=settings,
        )
        playwright_summary = run_playwright_fetch_for_approved_playwright_sources(
            connection,
            minio_client=minio_client,
            bucket=settings.minio_bucket,
            settings=settings,
        )

    print(
        "HTTP fetch complete:",
        f"attempted={http_summary['attempted']}",
        f"succeeded={http_summary['succeeded']}",
        f"failed={http_summary['failed']}",
    )
    print(
        "Scrapling fetch complete:",
        f"attempted={scrapling_summary['attempted']}",
        f"succeeded={scrapling_summary['succeeded']}",
        f"failed={scrapling_summary['failed']}",
    )
    print(
        "Playwright fetch complete:",
        f"attempted={playwright_summary['attempted']}",
        f"succeeded={playwright_summary['succeeded']}",
        f"failed={playwright_summary['failed']}",
    )
