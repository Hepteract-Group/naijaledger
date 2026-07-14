"""Tests for appropriation → budget_lines mapping and load (spec 0037)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from naijaledger.documents.service import get_document
from naijaledger.extractions.models import ExtractionCreate
from naijaledger.extractions.service import create_extraction
from naijaledger.finance.adapters import BUDGET_OFFICE_URL, adapter_for_source
from naijaledger.finance.budget_load import upsert_budget_line
from naijaledger.finance.budget_map import (
    NormalizedBudgetLine,
    infer_fiscal_year,
    map_docling_dict_to_budget_lines,
    map_table_grid_to_budget_lines,
)
from naijaledger.finance.normalize_load import run_normalize_load_for_document
from naijaledger.finance.ocds_models import ProvenanceContext
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source


def test_map_table_grid_and_amount_kobo() -> None:
    grid = [
        ["Code", "MDA", "Description", "Amount"],
        ["0220001", "Ministry of Works", "Road maintenance", "1,000,000.00"],
        ["0220002", "Ministry of Health", "Primary care", "250000"],
    ]
    lines = map_table_grid_to_budget_lines(grid, fiscal_year=2025)
    assert len(lines) == 2
    assert lines[0].code == "0220001"
    assert lines[0].agency_name == "Ministry of Works"
    assert lines[0].allocated_amount == 100_000_000
    assert lines[1].allocated_amount == 25_000_000


def test_thousands_header_scales_amount() -> None:
    grid = [
        ["Code", "MDA", "Description", "Amount (₦'000)"],
        ["01", "Works", "Bridges", "100"],
    ]
    lines = map_table_grid_to_budget_lines(grid, fiscal_year=2025)
    assert lines[0].allocated_amount == 10_000_000  # 100 * 1000 naira → kobo


def test_stable_synthetic_code_without_code_column() -> None:
    grid = [
        ["MDA", "Description", "Amount"],
        ["Works", "Bridges", "1000"],
    ]
    first = map_table_grid_to_budget_lines(grid, fiscal_year=2025)
    second = map_table_grid_to_budget_lines(grid, fiscal_year=2025)
    assert first[0].code.startswith("SYN-")
    assert first[0].code == second[0].code


def test_infer_fiscal_year() -> None:
    assert infer_fiscal_year("Appropriation Act 2025") == 2025
    assert infer_fiscal_year("no-year") is None


def test_map_docling_dict_tables() -> None:
    docling = {
        "tables": [
            {
                "data": {
                    "grid": [
                        [{"text": "Code"}, {"text": "Agency"}, {"text": "Amount"}],
                        [{"text": "01"}, {"text": "Finance"}, {"text": "5000"}],
                    ]
                },
                "prov": [{"page_no": 2}],
            }
        ]
    }
    lines = map_docling_dict_to_budget_lines(docling, fiscal_year=2024)
    assert len(lines) == 1
    assert lines[0].code == "01"
    assert lines[0].page == 2
    assert lines[0].allocated_amount == 500_000


def test_adapter_matches_budget_office_pdf() -> None:
    adapter = adapter_for_source(source_url=BUDGET_OFFICE_URL, document_format="pdf")
    assert adapter is not None
    assert adapter.load_kind == "budget"
    assert adapter.adapter_id == "budget-office-appropriation"


def _budget_source_and_pdf(db_connection: Connection, *, title: str = "Appropriation Act 2025"):
    existing = db_connection.execute(
        text("SELECT id FROM sources WHERE url = :url"),
        {"url": BUDGET_OFFICE_URL},
    ).first()
    if existing is None:
        source = create_source(
            db_connection,
            SourceCreate(
                name="Budget Office of the Federation — Budget Documents",
                jurisdiction="federal",
                category="budget",
                url=BUDGET_OFFICE_URL,
                fetch_method="http",
                format="html",
                added_by="test",
            ),
        )
        approve_source(db_connection, source.id, approved_by="human:test")
        source_id = source.id
    else:
        source_id = existing.id

    content_hash = uuid4().hex + uuid4().hex
    fetch_id = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, :sha, :key
            )
            RETURNING id
            """
        ),
        {
            "source_id": source_id,
            "url": BUDGET_OFFICE_URL,
            "sha": content_hash,
            "key": f"sha256/{content_hash}",
        },
    ).scalar_one()
    doc_id = db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key, title
            ) VALUES (
                :source_id, :fetch_id, :sha, 'pdf', :key, :title
            )
            RETURNING id
            """
        ),
        {
            "source_id": source_id,
            "fetch_id": fetch_id,
            "sha": content_hash,
            "key": f"sha256/{content_hash}",
            "title": title,
        },
    ).scalar_one()
    return source_id, get_document(db_connection, doc_id)


def test_upsert_budget_line_idempotent(db_connection: Connection) -> None:
    _source_id, document = _budget_source_and_pdf(db_connection)
    extraction = create_extraction(
        db_connection,
        ExtractionCreate(
            document_id=document.id,
            method="pdf_table",
            method_version="test",
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload={},
            content_type="application/pdf",
            content_type_conf=1.0,
            status="parsed",
        ),
    )
    line = NormalizedBudgetLine(
        fiscal_year=2025,
        agency_name="Test Budget Agency",
        code="TB-1",
        description="Pilot line",
        allocated_amount=10_000,
    )
    provenance = ProvenanceContext(
        document_id=document.id,
        extraction_id=extraction.id,
        method="pdf_table",
        derivation="extracted",
        confidence=1.0,
    )
    first = upsert_budget_line(db_connection, line, provenance=provenance)
    second = upsert_budget_line(db_connection, line, provenance=provenance)
    assert first == second
    count = db_connection.execute(
        text("SELECT count(*) FROM budget_lines WHERE code = 'TB-1'")
    ).scalar_one()
    assert count == 1
    edges = db_connection.execute(
        text(
            """
            SELECT count(*) FROM provenance_edges
            WHERE subject_type = 'budget_line' AND subject_id = :id
            """
        ),
        {"id": first},
    ).scalar_one()
    assert edges == 1


def test_normalize_load_budget_oversize_skip(db_connection: Connection) -> None:
    from naijaledger.config import Settings

    _source_id, document = _budget_source_and_pdf(db_connection)
    settings = Settings(budget_pdf_max_bytes=5)
    result = run_normalize_load_for_document(
        db_connection,
        document.id,
        minio_client=None,  # type: ignore[arg-type]
        bucket="unused",
        settings=settings,
        data_override=b"%PDF-1.4 oversized-bytes",
        fiscal_year_override=2025,
    )
    assert result["skipped"] is True
    assert result["reason"] == "pdf_too_large"


def test_normalize_load_budget_with_docling_override(db_connection: Connection) -> None:
    _source_id, document = _budget_source_and_pdf(db_connection)
    docling = {
        "tables": [
            {
                "data": {
                    "grid": [
                        [
                            {"text": "Code"},
                            {"text": "MDA"},
                            {"text": "Description"},
                            {"text": "Amount"},
                        ],
                        [
                            {"text": "1001"},
                            {"text": "Works"},
                            {"text": "Bridges"},
                            {"text": "1000"},
                        ],
                    ]
                },
                "prov": [{"page_no": 1}],
            }
        ]
    }
    result = run_normalize_load_for_document(
        db_connection,
        document.id,
        minio_client=None,  # type: ignore[arg-type]
        bucket="unused",
        data_override=b"%PDF-1.4 tiny",
        docling_override=docling,
        fiscal_year_override=2025,
        max_rows=10,
    )
    assert result["skipped"] is False
    assert result["budget_lines_upserted"] == 1
    row = db_connection.execute(
        text("SELECT code, allocated_amount FROM budget_lines WHERE code = '1001'")
    ).first()
    assert row is not None
    assert row.allocated_amount == 100_000
