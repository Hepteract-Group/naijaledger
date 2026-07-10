"""Read-only snapshots for anomaly rule evaluation (E7.1)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection


class RuleContext(BaseModel):
    tenders: list[dict[str, Any]] = Field(default_factory=list)
    awards: list[dict[str, Any]] = Field(default_factory=list)
    contracts: list[dict[str, Any]] = Field(default_factory=list)
    parties: list[dict[str, Any]] = Field(default_factory=list)
    payments: list[dict[str, Any]] = Field(default_factory=list)
    budget_lines: list[dict[str, Any]] = Field(default_factory=list)
    party_relationships: list[dict[str, Any]] = Field(default_factory=list)


def load_rule_context(connection: Connection) -> RuleContext:
    return RuleContext(
        tenders=_rows(
            connection,
            """
            SELECT id, ocid, agency_id, title, method, value_amount, currency,
                   bidding_opens_at, bidding_closes_at
            FROM tenders
            """,
        ),
        awards=_rows(
            connection,
            "SELECT id, tender_id, supplier_id, value_amount, currency, awarded_at FROM awards",
        ),
        contracts=_rows(
            connection,
            """
            SELECT id, award_id, supplier_id, agency_id, value_amount, currency,
                   signed_at, status
            FROM contracts
            """,
        ),
        parties=_rows(
            connection,
            """
            SELECT id, party_type, canonical_name, aliases, identifiers, address, merged_into_id
            FROM parties
            WHERE merged_into_id IS NULL
            """,
        ),
        payments=_rows(
            connection,
            """
            SELECT id, contract_id, agency_id, beneficiary_id, amount, currency, paid_at, purpose
            FROM payments
            """,
        ),
        budget_lines=_rows(
            connection,
            """
            SELECT id, fiscal_year, agency_id, code, allocated_amount, utilised_amount,
                   currency, jurisdiction
            FROM budget_lines
            """,
        ),
        party_relationships=_rows(
            connection,
            """
            SELECT id, from_party_id, to_party_id, relationship, weight
            FROM party_relationships
            """,
        ),
    )


def _rows(connection: Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(sql)).mappings()]


def as_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
