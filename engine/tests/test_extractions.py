from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from naijaledger.extractions.errors import ExtractionValidationError
from naijaledger.extractions.models import ExtractionCreate, ProvenanceEdgeCreate
from naijaledger.extractions.service import (
    create_extraction,
    create_provenance_edge,
    get_extraction,
    list_extractions_for_document,
    list_provenance_edges_for_extraction,
)
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import create_source


def _seed_document(db_connection):
    source = create_source(
        db_connection,
        SourceCreate(
            name="Extractions Schema Test",
            jurisdiction="federal",
            category="procurement",
            url="https://example.com/awards.xlsx",
            fetch_method="http",
            format="xlsx",
            added_by=SEED_ADDED_BY,
        ),
    )
    fetch_id = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, 'extract-hash', 'sha256/extract-hash'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "url": source.url},
    ).scalar_one()
    document_id = db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key
            ) VALUES (
                :source_id, :fetch_id, 'extract-hash', 'xlsx', 'sha256/extract-hash'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "fetch_id": fetch_id},
    ).scalar_one()
    return document_id


def test_extractions_table_columns(db_connection) -> None:
    rows = db_connection.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'extractions'
            ORDER BY ordinal_position
            """
        )
    ).all()
    columns = {record[0] for record in rows}
    assert {
        "document_id",
        "method",
        "method_version",
        "derivation",
        "confidence",
        "ok",
        "payload",
        "content_type",
        "content_type_conf",
        "status",
    }.issubset(columns)


def test_create_extracted_xlsx_with_confidence_1(db_connection) -> None:
    document_id = _seed_document(db_connection)
    extraction = create_extraction(
        db_connection,
        ExtractionCreate(
            document_id=document_id,
            method="xlsx",
            method_version="openpyxl-3.1",
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload={"blocks": [{"kind": "table", "rows": [["a", "b"]]}]},
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            content_type_conf=0.99,
            status="parsed",
        ),
    )
    loaded = get_extraction(db_connection, extraction.id)
    assert loaded.derivation == "extracted"
    assert loaded.confidence == Decimal("1.000")
    assert loaded.method == "xlsx"
    assert list_extractions_for_document(db_connection, document_id) == [loaded]


def test_inferred_requires_confidence_below_1(db_connection) -> None:
    document_id = _seed_document(db_connection)
    with pytest.raises(ExtractionValidationError):
        create_extraction(
            db_connection,
            ExtractionCreate(
                document_id=document_id,
                method="ocr",
                method_version="tesseract-5",
                derivation="inferred",
                confidence=1.0,
                ok=True,
                payload={"blocks": []},
                status="parsed",
            ),
        )


def test_extracted_rejects_confidence_below_1(db_connection) -> None:
    document_id = _seed_document(db_connection)
    with pytest.raises(ExtractionValidationError):
        create_extraction(
            db_connection,
            ExtractionCreate(
                document_id=document_id,
                method="json",
                method_version="stdlib-1",
                derivation="extracted",
                confidence=0.9,
                ok=True,
                payload={"blocks": []},
                status="parsed",
            ),
        )


def test_db_check_rejects_extracted_with_low_confidence(db_connection) -> None:
    document_id = _seed_document(db_connection)
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO extractions (
                        document_id, method, method_version, derivation, confidence,
                        ok, payload, status
                    ) VALUES (
                        :document_id, 'xlsx', 'v1', 'extracted', 0.5,
                        true, '{}'::jsonb, 'parsed'
                    )
                    """
                ),
                {"document_id": document_id},
            )


def test_quarantined_extraction(db_connection) -> None:
    document_id = _seed_document(db_connection)
    extraction = create_extraction(
        db_connection,
        ExtractionCreate(
            document_id=document_id,
            method="pdf_text",
            method_version="magika-router-1",
            derivation="ambiguous",
            confidence=0.2,
            ok=False,
            payload={"blocks": []},
            content_type="application/pdf",
            content_type_conf=0.3,
            status="quarantined",
        ),
    )
    assert extraction.status == "quarantined"
    assert extraction.ok is False


def test_provenance_edge_carries_derivation_confidence(db_connection) -> None:
    document_id = _seed_document(db_connection)
    extraction = create_extraction(
        db_connection,
        ExtractionCreate(
            document_id=document_id,
            method="pdf_table",
            method_version="docling-2.0",
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload={"blocks": [{"kind": "table"}]},
            status="parsed",
        ),
    )
    edge = create_provenance_edge(
        db_connection,
        ProvenanceEdgeCreate(
            document_id=document_id,
            extraction_id=extraction.id,
            method="pdf_table",
            derivation="extracted",
            confidence=1.0,
            page=1,
            region={"x0": 0.0, "y0": 0.0, "x1": 100.0, "y1": 50.0},
        ),
    )
    edges = list_provenance_edges_for_extraction(db_connection, extraction.id)
    assert len(edges) == 1
    assert edges[0].id == edge.id
    assert edges[0].derivation == "extracted"
    assert edges[0].confidence == Decimal("1.000")
    assert edges[0].page == 1
    assert edges[0].region == {"x0": 0.0, "y0": 0.0, "x1": 100.0, "y1": 50.0}
