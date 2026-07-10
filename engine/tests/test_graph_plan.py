from datetime import UTC, datetime
from uuid import uuid4

from naijaledger.finance.models import Party
from naijaledger.graph.plan import plan_finance_projection


def _party(
    *,
    name: str,
    party_type: str = "company",
    merged_into_id=None,
) -> Party:
    now = datetime.now(tz=UTC)
    return Party(
        id=uuid4(),
        party_type=party_type,  # type: ignore[arg-type]
        canonical_name=name,
        aliases=[],
        identifiers={},
        address=None,
        merged_into_id=merged_into_id,
        meta=None,
        created_at=now,
        updated_at=now,
    )


def test_plan_emits_agency_company_and_edges() -> None:
    agency = _party(name="Ministry", party_type="agency")
    company = _party(name="Supplier Co", party_type="company")
    tender_id = uuid4()
    award_id = uuid4()
    contract_id = uuid4()

    plan = plan_finance_projection(
        parties=[agency, company],
        tenders=[
            {
                "id": tender_id,
                "ocid": "ocds-1",
                "agency_id": agency.id,
                "title": "Widgets",
            }
        ],
        awards=[
            {
                "id": award_id,
                "tender_id": tender_id,
                "supplier_id": company.id,
            }
        ],
        contracts=[
            {
                "id": contract_id,
                "award_id": award_id,
                "agency_id": agency.id,
                "supplier_id": company.id,
                "status": "active",
            }
        ],
        canonical_ids={agency.id: agency.id, company.id: company.id},
    )

    labels = {tuple(node.labels) for node in plan.nodes}
    assert ("Agency", "Party") in labels
    assert ("Company", "Party") in labels
    assert ("Tender",) in labels
    rel_types = {rel.rel_type for rel in plan.relationships}
    assert {"ISSUED", "RESULTED_IN", "AWARDED_TO", "CONTRACTED", "SUPPLIED", "FROM_AWARD"} <= (
        rel_types
    )


def test_plan_skips_merged_party_nodes_and_resolves_fk() -> None:
    survivor = _party(name="Acme Surviving", party_type="company")
    merged = _party(name="Acme Old", party_type="company", merged_into_id=survivor.id)
    agency = _party(name="Agency", party_type="agency")
    tender_id = uuid4()
    award_id = uuid4()

    plan = plan_finance_projection(
        parties=[survivor, merged, agency],
        tenders=[
            {
                "id": tender_id,
                "ocid": None,
                "agency_id": agency.id,
                "title": "T",
            }
        ],
        awards=[
            {
                "id": award_id,
                "tender_id": tender_id,
                "supplier_id": merged.id,
            }
        ],
        contracts=[],
        canonical_ids={
            survivor.id: survivor.id,
            merged.id: survivor.id,
            agency.id: agency.id,
        },
    )

    party_ids = {node.properties["id"] for node in plan.nodes if "Party" in node.labels}
    assert str(survivor.id) in party_ids
    assert str(merged.id) not in party_ids

    awarded = [rel for rel in plan.relationships if rel.rel_type == "AWARDED_TO"]
    assert len(awarded) == 1
    assert awarded[0].end_id == survivor.id
