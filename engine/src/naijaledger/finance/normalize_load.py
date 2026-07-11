"""Run normalize_load: adapter → extraction → canonical finance upserts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from minio import Minio
from sqlalchemy.engine import Connection

from naijaledger.archive.storage import fetch_raw_bytes
from naijaledger.config import Settings, load_settings
from naijaledger.documents.service import get_document
from naijaledger.extractions.models import ExtractionCreate
from naijaledger.extractions.service import create_extraction
from naijaledger.finance.adapters import adapter_for_source
from naijaledger.finance.ocds import normalize_ocds_document
from naijaledger.finance.ocds_load import load_normalized_release
from naijaledger.finance.ocds_models import ProvenanceContext
from naijaledger.sources.service import get_source


def load_ocds_package(
    connection: Connection,
    package: dict[str, Any],
    *,
    document_id: UUID,
    method_version: str,
) -> dict[str, Any]:
    extraction = create_extraction(
        connection,
        ExtractionCreate(
            document_id=document_id,
            method="json",
            method_version=method_version,
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload=package,
            content_type="application/json",
            content_type_conf=1.0,
            status="parsed",
        ),
    )
    provenance = ProvenanceContext(
        document_id=document_id,
        extraction_id=extraction.id,
        method="json",
        derivation="extracted",
        confidence=1.0,
    )
    releases = normalize_ocds_document(package)
    tenders = 0
    parties = 0
    awards = 0
    for release in releases:
        result = load_normalized_release(connection, release, provenance=provenance)
        tenders += result.tenders_upserted
        parties += result.parties_upserted
        awards += len(result.award_ids)
    return {
        "extraction_id": str(extraction.id),
        "release_count": len(releases),
        "tenders_upserted": tenders,
        "parties_upserted": parties,
        "awards_upserted": awards,
    }


def run_normalize_load_for_document(
    connection: Connection,
    document_id: UUID,
    *,
    minio_client: Minio,
    bucket: str,
    settings: Settings | None = None,
    max_rows: int | None = None,
    data_override: bytes | None = None,
) -> dict[str, Any]:
    config = settings or load_settings()
    row_cap = config.normalize_load_max_rows if max_rows is None else max_rows
    document = get_document(connection, document_id)
    source = get_source(connection, document.source_id)
    adapter = adapter_for_source(source_url=source.url, document_format=document.format)
    if adapter is None:
        return {
            "skipped": True,
            "reason": "no_adapter",
            "document_id": str(document_id),
            "source_id": str(source.id),
        }

    data = (
        data_override
        if data_override is not None
        else fetch_raw_bytes(minio_client, bucket, document.archive_key)
    )
    package = adapter.to_package(data, max_rows=row_cap)
    loaded = load_ocds_package(
        connection,
        package,
        document_id=document.id,
        method_version=adapter.method_version,
    )
    return {
        "skipped": False,
        "adapter_id": adapter.adapter_id,
        "method_version": adapter.method_version,
        "document_id": str(document.id),
        "source_id": str(source.id),
        **loaded,
    }
