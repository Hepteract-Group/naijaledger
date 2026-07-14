"""Upsert appropriation budget_lines with provenance (spec 0037)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from naijaledger.extractions.models import ProvenanceEdgeCreate
from naijaledger.extractions.service import create_provenance_edge, find_provenance_edge
from naijaledger.finance.budget_map import NormalizedBudgetLine
from naijaledger.finance.ocds_models import ProvenanceContext


def _upsert_agency(connection: Connection, name: str) -> UUID:
    existing = connection.execute(
        text(
            """
            SELECT id FROM parties
            WHERE party_type = 'agency'
              AND lower(canonical_name) = lower(:name)
            """
        ),
        {"name": name},
    ).first()
    if existing is not None:
        return UUID(str(existing.id))
    inserted = connection.execute(
        text(
            """
            INSERT INTO parties (party_type, canonical_name, aliases, identifiers)
            VALUES ('agency', :name, CAST(:aliases AS text[]), CAST(:identifiers AS jsonb))
            RETURNING id
            """
        ),
        {"name": name, "aliases": "{}", "identifiers": "{}"},
    ).scalar_one()
    return UUID(str(inserted))


def _link_budget_line(
    connection: Connection,
    provenance: ProvenanceContext,
    *,
    budget_line_id: UUID,
) -> None:
    existing = find_provenance_edge(
        connection,
        extraction_id=provenance.extraction_id,
        subject_type="budget_line",
        subject_id=budget_line_id,
    )
    if existing is not None:
        return
    create_provenance_edge(
        connection,
        ProvenanceEdgeCreate(
            document_id=provenance.document_id,
            extraction_id=provenance.extraction_id,
            method=provenance.method,
            derivation=provenance.derivation,
            confidence=provenance.confidence,
            page=provenance.page,
            region=provenance.region,
            subject_type="budget_line",
            subject_id=budget_line_id,
        ),
    )


def upsert_budget_line(
    connection: Connection,
    line: NormalizedBudgetLine,
    *,
    provenance: ProvenanceContext | None = None,
) -> UUID:
    agency_id = _upsert_agency(connection, line.agency_name)
    row_id = connection.execute(
        text(
            """
            INSERT INTO budget_lines (
                fiscal_year, agency_id, code, description,
                allocated_amount, currency, jurisdiction, region, meta
            ) VALUES (
                :fiscal_year, :agency_id, :code, :description,
                :allocated_amount, 'NGN', :jurisdiction, NULL,
                CAST(:meta AS jsonb)
            )
            ON CONFLICT ON CONSTRAINT uq_budget_lines_natural DO UPDATE SET
                description = EXCLUDED.description,
                allocated_amount = EXCLUDED.allocated_amount,
                updated_at = now()
            RETURNING id
            """
        ),
        {
            "fiscal_year": line.fiscal_year,
            "agency_id": agency_id,
            "code": line.code,
            "description": line.description,
            "allocated_amount": line.allocated_amount,
            "jurisdiction": line.jurisdiction,
            "meta": "null",
        },
    ).scalar_one()
    row = UUID(str(row_id))
    if provenance is not None:
        page_prov = ProvenanceContext(
            document_id=provenance.document_id,
            extraction_id=provenance.extraction_id,
            method=provenance.method,
            derivation=provenance.derivation,
            confidence=provenance.confidence,
            page=line.page if line.page is not None else provenance.page,
            region=provenance.region,
        )
        _link_budget_line(connection, page_prov, budget_line_id=row)
    return row


def load_budget_lines(
    connection: Connection,
    lines: list[NormalizedBudgetLine],
    *,
    provenance: ProvenanceContext,
) -> dict[str, Any]:
    ids: list[UUID] = []
    for line in lines:
        ids.append(upsert_budget_line(connection, line, provenance=provenance))
    return {
        "budget_lines_upserted": len(ids),
        "budget_line_ids": [str(item) for item in ids],
    }
