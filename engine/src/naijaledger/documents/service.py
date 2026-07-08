import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.documents.errors import DocumentNotFoundError
from naijaledger.documents.models import Document, DocumentUpsertResult
from naijaledger.sources.types import SourceFormat

_DOCUMENT_COLUMNS = """
    id, source_id, first_fetch_id, sha256, format, archive_key, title,
    published_at, meta, created_at, updated_at
"""


def _row_to_document(row: Row[Any]) -> Document:
    mapping = row._mapping
    return Document(
        id=mapping["id"],
        source_id=mapping["source_id"],
        first_fetch_id=mapping["first_fetch_id"],
        sha256=mapping["sha256"],
        format=mapping["format"],
        archive_key=mapping["archive_key"],
        title=mapping["title"],
        published_at=mapping["published_at"],
        meta=mapping["meta"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def get_document_by_sha256(connection: Connection, sha256: str) -> Document | None:
    query = text(
        f"""
        SELECT {_DOCUMENT_COLUMNS}
        FROM documents
        WHERE sha256 = :sha256
        """
    )
    row = connection.execute(query, {"sha256": sha256}).first()
    if row is None:
        return None
    return _row_to_document(row)


def get_document(connection: Connection, document_id: UUID) -> Document:
    query = text(
        f"""
        SELECT {_DOCUMENT_COLUMNS}
        FROM documents
        WHERE id = :id
        """
    )
    try:
        row = connection.execute(query, {"id": document_id}).one()
    except NoResultFound as exc:
        raise DocumentNotFoundError(str(document_id)) from exc
    return _row_to_document(row)


def upsert_document_from_fetch(
    connection: Connection,
    *,
    source_id: UUID,
    first_fetch_id: UUID,
    sha256: str,
    archive_key: str,
    format: SourceFormat,
    title: str | None = None,
    meta: dict[str, Any] | None = None,
) -> DocumentUpsertResult:
    insert_query = text(
        f"""
        INSERT INTO documents (
            source_id, first_fetch_id, sha256, format, archive_key, title, meta
        ) VALUES (
            :source_id, :first_fetch_id, :sha256, :format, :archive_key, :title,
            CAST(:meta AS jsonb)
        )
        ON CONFLICT (sha256) DO NOTHING
        RETURNING {_DOCUMENT_COLUMNS}
        """
    )
    row = connection.execute(
        insert_query,
        {
            "source_id": source_id,
            "first_fetch_id": first_fetch_id,
            "sha256": sha256,
            "format": format,
            "archive_key": archive_key,
            "title": title,
            "meta": json.dumps(meta) if meta is not None else None,
        },
    ).first()

    if row is not None:
        document = _row_to_document(row)
        return DocumentUpsertResult(document_id=document.id, created=True)

    existing = get_document_by_sha256(connection, sha256)
    if existing is None:
        msg = f"document upsert failed for sha256 {sha256}"
        raise RuntimeError(msg)

    return DocumentUpsertResult(document_id=existing.id, created=False)
