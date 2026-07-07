import logging

from naijaledger.archive.storage import create_minio_client, ensure_archive_bucket
from naijaledger.config import load_settings


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    client = create_minio_client(settings)
    ensure_archive_bucket(
        client,
        settings.minio_bucket,
        retention_days=settings.minio_retention_days,
    )
    print(f"Archive bucket ready: {settings.minio_bucket}")
