import pytest
from minio import Minio

from naijaledger.archive.storage import (
    archive_object_key,
    content_hash,
    create_minio_client,
    ensure_archive_bucket,
    fetch_raw_bytes,
    minio_reachable,
    store_raw_bytes,
)
from naijaledger.config import load_settings


def test_archive_object_key_format() -> None:
    digest = "a" * 64
    assert archive_object_key(digest) == f"sha256/{digest}"


def test_content_hash_is_sha256_hex() -> None:
    data = b"naijaledger archive test"
    assert content_hash(data) == content_hash(data)
    assert len(content_hash(data)) == 64


@pytest.mark.integration
def test_store_and_fetch_round_trip() -> None:
    if not minio_reachable():
        pytest.skip("MinIO integration tests disabled or unreachable")

    settings = load_settings()
    client = create_minio_client(settings)
    ensure_archive_bucket(
        client,
        settings.minio_bucket,
        retention_days=settings.minio_retention_days,
    )

    payload = b"immutable raw bytes for WORM archive"
    first = store_raw_bytes(client, settings.minio_bucket, payload)
    second = store_raw_bytes(client, settings.minio_bucket, payload)

    assert first["created"] is True
    assert second["created"] is False
    assert first["archive_key"] == second["archive_key"]
    assert first["content_hash"] == content_hash(payload)
    assert fetch_raw_bytes(client, settings.minio_bucket, first["archive_key"]) == payload


@pytest.mark.integration
def test_ensure_archive_bucket_is_idempotent() -> None:
    if not minio_reachable():
        pytest.skip("MinIO integration tests disabled or unreachable")

    settings = load_settings()
    client = create_minio_client(settings)
    ensure_archive_bucket(
        client,
        settings.minio_bucket,
        retention_days=settings.minio_retention_days,
    )
    ensure_archive_bucket(
        client,
        settings.minio_bucket,
        retention_days=settings.minio_retention_days,
    )

    assert isinstance(client, Minio)
