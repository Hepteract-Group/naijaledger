"""Ops wrapper: fetch Ekiti (optional) then normalize_load via shared pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from naijaledger.archive.storage import create_minio_client
from naijaledger.config import load_settings
from naijaledger.db.connection import create_db_engine
from naijaledger.documents.models import Document
from naijaledger.documents.service import get_document
from naijaledger.fetch.scrapling_fetch import scrapling_fetch_source
from naijaledger.finance.adapters import EKITI_URL
from naijaledger.finance.normalize_load import run_normalize_load_for_document
from naijaledger.http.client import create_http_client
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import list_sources

logger = logging.getLogger("naijaledger.finance.portal_load")


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


def run_ekiti_vertical_slice(
    engine: Engine,
    *,
    fetch: bool = True,
    max_rows: int = 100,
    html_path: Path | None = None,
) -> dict[str, Any]:
    """Thin ops path — prefer jobs worker in production."""
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

        minio = create_minio_client(settings)
        summary = run_normalize_load_for_document(
            connection,
            document.id,
            minio_client=minio,
            bucket=settings.minio_bucket,
            settings=settings,
            max_rows=max_rows,
            data_override=html_path.read_bytes() if html_path is not None else None,
        )
        return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ops wrapper: Ekiti fetch + normalize_load (prefer naijaledger-jobs)",
    )
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
    logger.info("Ekiti portal-load wrapper complete: %s", summary)
    print(summary)


if __name__ == "__main__":
    run()
