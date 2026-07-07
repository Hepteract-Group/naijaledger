import hashlib
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from urllib.parse import urlparse

from minio.commonconfig import COMPLIANCE
from minio import Minio
from minio.error import S3Error
from minio.retention import Retention

from naijaledger.archive.types import ArchiveStoreResult
from naijaledger.config import Settings, load_settings

_OBJECT_PREFIX = "sha256"


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_object_key(digest: str) -> str:
    return f"{_OBJECT_PREFIX}/{digest}"


def parse_minio_endpoint(endpoint: str) -> tuple[str, bool]:
    if "://" in endpoint:
        parsed = urlparse(endpoint)
        host = parsed.netloc or parsed.path
        secure = parsed.scheme == "https"
        return host, secure
    return endpoint, False


def create_minio_client(settings: Settings | None = None) -> Minio:
    config = settings or load_settings()
    host, secure = parse_minio_endpoint(config.minio_endpoint)
    return Minio(
        host,
        access_key=config.minio_access_key,
        secret_key=config.minio_secret_key,
        secure=secure,
    )


def ensure_archive_bucket(
    client: Minio,
    bucket: str,
    *,
    retention_days: int,
) -> None:
    if client.bucket_exists(bucket):
        return
    client.make_bucket(bucket, object_lock=True)
    _ = retention_days  # retention applied per-object on put


def object_exists(client: Minio, bucket: str, archive_key: str) -> bool:
    try:
        client.stat_object(bucket, archive_key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            return False
        raise
    return True


def store_raw_bytes(
    client: Minio,
    bucket: str,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
    retention_days: int | None = None,
) -> ArchiveStoreResult:
    digest = content_hash(data)
    archive_key = archive_object_key(digest)
    days = retention_days if retention_days is not None else load_settings().minio_retention_days

    if object_exists(client, bucket, archive_key):
        return ArchiveStoreResult(
            archive_key=archive_key,
            content_hash=digest,
            byte_count=len(data),
            created=False,
        )

    retain_until = datetime.now(tz=UTC) + timedelta(days=days)
    retention = Retention(COMPLIANCE, retain_until_date=retain_until)
    client.put_object(
        bucket,
        archive_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
        retention=retention,
    )
    return ArchiveStoreResult(
        archive_key=archive_key,
        content_hash=digest,
        byte_count=len(data),
        created=True,
    )


def fetch_raw_bytes(client: Minio, bucket: str, archive_key: str) -> bytes:
    response = client.get_object(bucket, archive_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def minio_reachable(settings: Settings | None = None) -> bool:
    config = settings or load_settings()
    if os.environ.get("MINIO_INTEGRATION_TESTS", "").lower() not in {"1", "true", "yes"}:
        return False
    client = create_minio_client(config)
    try:
        client.bucket_exists(config.minio_bucket)
    except Exception:
        return False
    return True
