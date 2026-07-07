import logging

from naijaledger.archive.storage import create_minio_client, ensure_archive_bucket
from naijaledger.config import load_settings
from naijaledger.db.connection import create_db_engine
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
        summary = run_static_fetch_for_approved_http_sources(
            connection,
            minio_client=minio_client,
            bucket=settings.minio_bucket,
        )

    print(
        "Static fetch complete:",
        f"attempted={summary['attempted']}",
        f"succeeded={summary['succeeded']}",
        f"failed={summary['failed']}",
    )
