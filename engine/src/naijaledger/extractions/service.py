import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.extractions.errors import (
    ExtractionValidationError,
    validate_derivation_confidence,
)
from naijaledger.extractions.models import (
    Extraction,
    ExtractionCreate,
    ProvenanceEdge,
    ProvenanceEdgeCreate,
)

_EXTRACTION_COLUMNS = """
    id, document_id, method, method_version, derivation, confidence, ok, payload,
    content_type, content_type_conf, status, created_at, updated_at
"""

_PROVENANCE_COLUMNS = """
    id, subject_type, subject_id, document_id, extraction_id, page, region, method,
    derivation, confidence, verified_by, verified_at, created_at, updated_at
"""


class ExtractionNotFoundError(LookupError):
    pass


def _row_to_extraction(row: Row[Any]) -> Extraction:
    mapping = row._mapping
    return Extraction(
        id=mapping["id"],
        document_id=mapping["document_id"],
        method=mapping["method"],
        method_version=mapping["method_version"],
        derivation=mapping["derivation"],
        confidence=mapping["confidence"],
        ok=mapping["ok"],
        payload=mapping["payload"],
        content_type=mapping["content_type"],
        content_type_conf=mapping["content_type_conf"],
        status=mapping["status"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def _row_to_provenance_edge(row: Row[Any]) -> ProvenanceEdge:
    mapping = row._mapping
    return ProvenanceEdge(
        id=mapping["id"],
        subject_type=mapping["subject_type"],
        subject_id=mapping["subject_id"],
        document_id=mapping["document_id"],
        extraction_id=mapping["extraction_id"],
        page=mapping["page"],
        region=mapping["region"],
        method=mapping["method"],
        derivation=mapping["derivation"],
        confidence=mapping["confidence"],
        verified_by=mapping["verified_by"],
        verified_at=mapping["verified_at"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def get_extraction(connection: Connection, extraction_id: UUID) -> Extraction:
    query = text(
        f"""
        SELECT {_EXTRACTION_COLUMNS}
        FROM extractions
        WHERE id = :id
        """
    )
    try:
        row = connection.execute(query, {"id": extraction_id}).one()
    except NoResultFound as exc:
        raise ExtractionNotFoundError(str(extraction_id)) from exc
    return _row_to_extraction(row)


def list_extractions_for_document(
    connection: Connection,
    document_id: UUID,
) -> list[Extraction]:
    query = text(
        f"""
        SELECT {_EXTRACTION_COLUMNS}
        FROM extractions
        WHERE document_id = :document_id
        ORDER BY created_at ASC
        """
    )
    rows = connection.execute(query, {"document_id": document_id}).all()
    return [_row_to_extraction(row) for row in rows]


def create_extraction(connection: Connection, data: ExtractionCreate) -> Extraction:
    validate_derivation_confidence(data.derivation, data.confidence)
    query = text(
        f"""
        INSERT INTO extractions (
            document_id, method, method_version, derivation, confidence, ok,
            payload, content_type, content_type_conf, status
        ) VALUES (
            :document_id, :method, :method_version, :derivation, :confidence, :ok,
            CAST(:payload AS jsonb), :content_type, :content_type_conf, :status
        )
        RETURNING {_EXTRACTION_COLUMNS}
        """
    )
    row = connection.execute(
        query,
        {
            "document_id": data.document_id,
            "method": data.method,
            "method_version": data.method_version,
            "derivation": data.derivation,
            "confidence": data.confidence,
            "ok": data.ok,
            "payload": json.dumps(data.payload),
            "content_type": data.content_type,
            "content_type_conf": data.content_type_conf,
            "status": data.status,
        },
    ).one()
    return _row_to_extraction(row)


def create_provenance_edge(
    connection: Connection,
    data: ProvenanceEdgeCreate,
) -> ProvenanceEdge:
    validate_derivation_confidence(data.derivation, data.confidence)
    query = text(
        f"""
        INSERT INTO provenance_edges (
            subject_type, subject_id, document_id, extraction_id, page, region,
            method, derivation, confidence
        ) VALUES (
            :subject_type, :subject_id, :document_id, :extraction_id, :page,
            CAST(:region AS jsonb), :method, :derivation, :confidence
        )
        RETURNING {_PROVENANCE_COLUMNS}
        """
    )
    row = connection.execute(
        query,
        {
            "subject_type": data.subject_type,
            "subject_id": data.subject_id,
            "document_id": data.document_id,
            "extraction_id": data.extraction_id,
            "page": data.page,
            "region": json.dumps(data.region) if data.region is not None else None,
            "method": data.method,
            "derivation": data.derivation,
            "confidence": data.confidence,
        },
    ).one()
    return _row_to_provenance_edge(row)


def list_provenance_edges_for_extraction(
    connection: Connection,
    extraction_id: UUID,
) -> list[ProvenanceEdge]:
    query = text(
        f"""
        SELECT {_PROVENANCE_COLUMNS}
        FROM provenance_edges
        WHERE extraction_id = :extraction_id
        ORDER BY created_at ASC
        """
    )
    rows = connection.execute(query, {"extraction_id": extraction_id}).all()
    return [_row_to_provenance_edge(row) for row in rows]


__all__ = [
    "ExtractionNotFoundError",
    "ExtractionValidationError",
    "create_extraction",
    "create_provenance_edge",
    "get_extraction",
    "list_extractions_for_document",
    "list_provenance_edges_for_extraction",
]
