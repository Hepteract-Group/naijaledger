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
from naijaledger.finance.budget_load import load_budget_lines
from naijaledger.finance.budget_map import infer_fiscal_year, map_docling_dict_to_budget_lines
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


def load_budget_pdf(
    connection: Connection,
    data: bytes,
    *,
    document_id: UUID,
    method_version: str,
    fiscal_year: int,
    max_rows: int | None,
    docling_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if docling_override is not None:
        docling_dict = docling_override
    else:
        from tempfile import NamedTemporaryFile

        from docling.document_converter import DocumentConverter

        with NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(data)
            tmp.flush()
            converted = DocumentConverter().convert(tmp.name)
            docling_dict = converted.document.export_to_dict()

    lines = map_docling_dict_to_budget_lines(
        docling_dict,
        fiscal_year=fiscal_year,
        max_rows=max_rows,
    )
    extraction = create_extraction(
        connection,
        ExtractionCreate(
            document_id=document_id,
            method="pdf_table",
            method_version=method_version,
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload={"fiscal_year": fiscal_year, "line_count": len(lines)},
            content_type="application/pdf",
            content_type_conf=1.0,
            status="parsed",
        ),
    )
    provenance = ProvenanceContext(
        document_id=document_id,
        extraction_id=extraction.id,
        method="pdf_table",
        derivation="extracted",
        confidence=1.0,
    )
    loaded = load_budget_lines(connection, lines, provenance=provenance)
    return {
        "extraction_id": str(extraction.id),
        "fiscal_year": fiscal_year,
        **loaded,
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
    docling_override: dict[str, Any] | None = None,
    fiscal_year_override: int | None = None,
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

    if adapter.load_kind == "budget":
        if len(data) > config.budget_pdf_max_bytes:
            return {
                "skipped": True,
                "reason": "pdf_too_large",
                "document_id": str(document_id),
                "source_id": str(source.id),
                "byte_length": len(data),
                "max_bytes": config.budget_pdf_max_bytes,
            }
        year = fiscal_year_override or infer_fiscal_year(
            document.title,
            source.name,
            source.url,
        )
        if year is None:
            return {
                "skipped": True,
                "reason": "fiscal_year_unknown",
                "document_id": str(document_id),
                "source_id": str(source.id),
            }
        loaded = load_budget_pdf(
            connection,
            data,
            document_id=document.id,
            method_version=adapter.method_version,
            fiscal_year=year,
            max_rows=row_cap,
            docling_override=docling_override,
        )
        return {
            "skipped": False,
            "adapter_id": adapter.adapter_id,
            "method_version": adapter.method_version,
            "document_id": str(document.id),
            "source_id": str(source.id),
            **loaded,
        }

    if adapter.to_package is None:
        return {
            "skipped": True,
            "reason": "no_package_converter",
            "document_id": str(document_id),
            "source_id": str(source.id),
        }
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
