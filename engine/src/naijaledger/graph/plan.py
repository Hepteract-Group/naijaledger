"""Pure finance → graph plan (E6.4). No I/O."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from naijaledger.finance.models import Party


class GraphNode(BaseModel):
    labels: list[str]
    properties: dict[str, Any]


class GraphRel(BaseModel):
    rel_type: str
    start_label: str
    start_id: UUID
    end_label: str
    end_id: UUID
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphPlan(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    relationships: list[GraphRel] = Field(default_factory=list)


def _party_label(party_type: str) -> str:
    if party_type == "agency":
        return "Agency"
    if party_type == "person":
        return "Person"
    return "Company"


def _node(labels: list[str], *, id: UUID, **props: Any) -> GraphNode:
    properties = {"id": str(id), **props}
    return GraphNode(labels=labels, properties=properties)


def plan_finance_projection(
    *,
    parties: list[Party],
    tenders: list[dict[str, Any]],
    awards: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    canonical_ids: dict[UUID, UUID],
) -> GraphPlan:
    """Build a graph plan from finance rows.

    `canonical_ids` maps any party id → survivor id (identity for unmerged).
    Parties with `merged_into_id` set are omitted as nodes.
    """
    nodes: list[GraphNode] = []
    relationships: list[GraphRel] = []
    label_by_party: dict[UUID, str] = {}

    for party in parties:
        if party.merged_into_id is not None:
            continue
        label = _party_label(party.party_type)
        label_by_party[party.id] = label
        nodes.append(
            _node(
                [label, "Party"],
                id=party.id,
                name=party.canonical_name,
                party_type=party.party_type,
            )
        )

    tender_ids: set[UUID] = set()
    for tender in tenders:
        tender_id = tender["id"]
        tender_ids.add(tender_id)
        nodes.append(
            _node(
                ["Tender"],
                id=tender_id,
                ocid=tender.get("ocid"),
                title=tender["title"],
            )
        )
        agency_id = canonical_ids[tender["agency_id"]]
        agency_label = label_by_party.get(agency_id, "Agency")
        relationships.append(
            GraphRel(
                rel_type="ISSUED",
                start_label=agency_label,
                start_id=agency_id,
                end_label="Tender",
                end_id=tender_id,
            )
        )

    for award in awards:
        award_id = award["id"]
        nodes.append(_node(["Award"], id=award_id))
        tender_id = award["tender_id"]
        if tender_id in tender_ids:
            relationships.append(
                GraphRel(
                    rel_type="RESULTED_IN",
                    start_label="Tender",
                    start_id=tender_id,
                    end_label="Award",
                    end_id=award_id,
                )
            )
        supplier_id = canonical_ids[award["supplier_id"]]
        supplier_label = label_by_party.get(supplier_id, "Company")
        relationships.append(
            GraphRel(
                rel_type="AWARDED_TO",
                start_label="Award",
                start_id=award_id,
                end_label=supplier_label,
                end_id=supplier_id,
            )
        )

    for contract in contracts:
        contract_id = contract["id"]
        nodes.append(
            _node(
                ["Contract"],
                id=contract_id,
                status=contract.get("status"),
            )
        )
        award_id = contract.get("award_id")
        if award_id is not None:
            relationships.append(
                GraphRel(
                    rel_type="FROM_AWARD",
                    start_label="Contract",
                    start_id=contract_id,
                    end_label="Award",
                    end_id=award_id,
                )
            )
        agency_id = canonical_ids[contract["agency_id"]]
        agency_label = label_by_party.get(agency_id, "Agency")
        relationships.append(
            GraphRel(
                rel_type="CONTRACTED",
                start_label=agency_label,
                start_id=agency_id,
                end_label="Contract",
                end_id=contract_id,
            )
        )
        supplier_id = canonical_ids[contract["supplier_id"]]
        supplier_label = label_by_party.get(supplier_id, "Company")
        relationships.append(
            GraphRel(
                rel_type="SUPPLIED",
                start_label=supplier_label,
                start_id=supplier_id,
                end_label="Contract",
                end_id=contract_id,
            )
        )

    return GraphPlan(nodes=nodes, relationships=relationships)
