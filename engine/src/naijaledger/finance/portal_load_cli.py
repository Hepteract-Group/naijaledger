"""Load Ekiti-style portal HTML into canonical finance tables (vertical slice)."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from naijaledger.archive.storage import create_minio_client, fetch_raw_bytes
from naijaledger.config import load_settings
from naijaledger.db.connection import create_db_engine
from naijaledger.documents.models import Document
from naijaledger.documents.service import get_document
from naijaledger.extractions.models import ExtractionCreate
from naijaledger.extractions.service import create_extraction
from naijaledger.fetch.scrapling_fetch import scrapling_fetch_source
from naijaledger.finance.html_portal import ekiti_html_to_ocds_package
from naijaledger.finance.ocds import normalize_ocds_document
from naijaledger.finance.ocds_load import load_normalized_release
from naijaledger.finance.ocds_models import ProvenanceContext
from naijaledger.http.client import create_http_client
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import list_sources

logger = logging.getLogger("naijaledger.finance.portal_load")

EKITI_URL = "https://ocdsportal.azurewebsites.net/Home/Procurements"
METHOD_VERSION = "ekiti-html-table-1"


def _latest_html_document(connection: Connection, source_id: UUID) -> Document | None:
    row = connection.execute(
        text(
            """
            SELECT id
            FROM documents
            WHERE source_id = :source_id AND format = 'html'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"source_id": source_id},
    ).first()
    if row is None:
        return None
    return get_document(connection, row.id)


def find_ekiti_source(connection: Connection) -> SourceRecord:
    for source in list_sources(connection):
        if source.url.rstrip("/") == EKITI_URL.rstrip("/"):
            return source
    msg = f"Ekiti source not seeded: {EKITI_URL}"
    raise RuntimeError(msg)


def load_ekiti_html(
    connection: Connection,
    html: bytes,
    *,
    document_id: UUID,
    max_rows: int | None = 100,
) -> dict[str, Any]:
    package = ekiti_html_to_ocds_package(html, max_rows=max_rows)
    extraction = create_extraction(
        connection,
        ExtractionCreate(
            document_id=document_id,
            method="json",
            method_version=METHOD_VERSION,
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload=package,
            content_type="text/html",
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


def run_ekiti_vertical_slice(
    engine: Engine,
    *,
    fetch: bool = True,
    max_rows: int = 100,
    html_path: Path | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    with engine.begin() as connection:
        source = find_ekiti_source(connection)
        if source.status != "approved":
            msg = f"Ekiti source {source.id} is not approved (status={source.status})"
            raise RuntimeError(msg)

        if fetch and html_path is None:
            minio = create_minio_client(settings)
            with create_http_client(settings) as http_client:
                result = scrapling_fetch_source(
                    connection,
                    source,
                    minio_client=minio,
                    bucket=settings.minio_bucket,
                    settings=settings,
                    http_client=http_client,
                )
            if not result["ok"] or result["document_id"] is None:
                msg = f"Ekiti fetch failed: {result}"
                raise RuntimeError(msg)

        document = _latest_html_document(connection, source.id)
        if document is None:
            msg = "no HTML document archived for Ekiti source"
            raise RuntimeError(msg)

        if html_path is not None:
            html = html_path.read_bytes()
        else:
            minio = create_minio_client(settings)
            html = fetch_raw_bytes(minio, settings.minio_bucket, document.archive_key)

        summary = load_ekiti_html(
            connection,
            html,
            document_id=document.id,
            max_rows=max_rows,
        )
        summary["source_id"] = str(source.id)
        summary["document_id"] = str(document.id)
        return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load Ekiti portal HTML into finance tables")
    parser.add_argument("--max-rows", type=int, default=100, help="Cap releases loaded")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Use latest archived HTML document instead of fetching",
    )
    parser.add_argument(
        "--html-path",
        type=Path,
        help="Override archive bytes with a local HTML file (document row still required)",
    )
    return parser


def run(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args(argv)
    engine = create_db_engine()
    summary = run_ekiti_vertical_slice(
        engine,
        fetch=not args.no_fetch and args.html_path is None,
        max_rows=args.max_rows,
        html_path=args.html_path,
    )
    logger.info("Ekiti vertical slice complete: %s", summary)
    print(summary)


if __name__ == "__main__":
    run()
