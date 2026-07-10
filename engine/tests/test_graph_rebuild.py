import os

import pytest
from sqlalchemy import text

from naijaledger.finance.models import PartyCreate
from naijaledger.finance.service import create_party
from naijaledger.graph.client import MemgraphClient, memgraph_reachable
from naijaledger.graph.rebuild import rebuild_finance_graph

pytestmark = pytest.mark.skipif(
    not memgraph_reachable(),
    reason="Memgraph not reachable (set MEMGRAPH_URI / start docker compose memgraph)",
)


def test_rebuild_finance_graph_idempotent(db_connection) -> None:
    agency = create_party(
        db_connection,
        PartyCreate(party_type="agency", canonical_name="Graph Agency"),
    )
    company = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Graph Supplier"),
    )
    tender_id = db_connection.execute(
        text(
            """
            INSERT INTO tenders (ocid, agency_id, title)
            VALUES ('ocds-graph-1', :agency_id, 'Graph Tender')
            RETURNING id
            """
        ),
        {"agency_id": agency.id},
    ).scalar_one()
    db_connection.execute(
        text(
            """
            INSERT INTO awards (tender_id, supplier_id, value_amount)
            VALUES (:tender_id, :supplier_id, 1000)
            """
        ),
        {"tender_id": tender_id, "supplier_id": company.id},
    )

    client = MemgraphClient.from_url(os.environ.get("MEMGRAPH_URI"))
    try:
        first = rebuild_finance_graph(db_connection, client)
        second = rebuild_finance_graph(db_connection, client)
        assert first.nodes == second.nodes
        assert first.relationships == second.relationships
        assert client.count_nodes(("FinanceParty", "Tender", "Award")) >= 3
    finally:
        client.close()
