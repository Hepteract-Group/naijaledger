"""Rebuild Memgraph finance projection from Postgres (E6.4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from naijaledger.finance.models import Party
from naijaledger.finance.service import canonical_party_id
from naijaledger.graph.client import GraphClient
from naijaledger.graph.plan import GraphPlan, plan_finance_projection

_PARTY_COLUMNS = """
    id, party_type, canonical_name, aliases, identifiers, address, merged_into_id,
    meta, created_at, updated_at
"""


class RebuildStats(BaseModel):
    nodes: int
    relationships: int


def _row_to_party(mapping: Any) -> Party:
    return Party(
        id=mapping["id"],
        party_type=mapping["party_type"],
        canonical_name=mapping["canonical_name"],
        aliases=list(mapping["aliases"] or []),
        identifiers=mapping["identifiers"] or {},
        address=mapping["address"],
        merged_into_id=mapping["merged_into_id"],
        meta=mapping["meta"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def _load_parties(connection: Connection) -> list[Party]:
    rows = connection.execute(text(f"SELECT {_PARTY_COLUMNS} FROM parties")).all()
    return [_row_to_party(row._mapping) for row in rows]


def _load_tenders(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(text("SELECT id, ocid, agency_id, title FROM tenders")).mappings()
    return [dict(row) for row in rows]


def _load_awards(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(text("SELECT id, tender_id, supplier_id FROM awards")).mappings()
    return [dict(row) for row in rows]


def _load_contracts(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        text("SELECT id, award_id, supplier_id, agency_id, status FROM contracts")
    ).mappings()
    return [dict(row) for row in rows]


def _canonical_map(connection: Connection, parties: list[Party]) -> dict[UUID, UUID]:
    mapping: dict[UUID, UUID] = {}
    for party in parties:
        mapping[party.id] = canonical_party_id(connection, party.id)
    return mapping


def build_finance_plan(connection: Connection) -> GraphPlan:
    parties = _load_parties(connection)
    return plan_finance_projection(
        parties=parties,
        tenders=_load_tenders(connection),
        awards=_load_awards(connection),
        contracts=_load_contracts(connection),
        canonical_ids=_canonical_map(connection, parties),
    )


def rebuild_finance_graph(connection: Connection, graph: GraphClient) -> RebuildStats:
    plan = build_finance_plan(connection)
    rebuild = getattr(graph, "rebuild_from_plan", None)
    if callable(rebuild):
        rebuild(plan)
    else:
        graph.wipe_finance_projection()
        graph.apply_plan(plan)
    return RebuildStats(nodes=len(plan.nodes), relationships=len(plan.relationships))
