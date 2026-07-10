from uuid import uuid4

from sqlalchemy import text

from naijaledger.agents.models import AgentContext, register_tools
from naijaledger.agents.runtime import run_agent
from naijaledger.agents.smoke import EchoToolsAgent, NeverFinishAgent
from naijaledger.agents.tools import (
    LookupPartyTool,
    SearchDocumentsTool,
    default_tools,
)
from naijaledger.finance.models import PartyCreate
from naijaledger.finance.service import create_party
from naijaledger.graph.client import memgraph_reachable


def test_default_tools_unique_read_only() -> None:
    tools = default_tools()
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names))
    assert set(names) == {
        "lookup_party",
        "lookup_flag",
        "list_open_flags",
        "search_documents",
        "graph_neighbors",
    }


def test_run_agent_smoke_with_fake_tool() -> None:
    class FakeListFlags:
        name = "list_open_flags"

        def run(self, ctx, args):
            from naijaledger.agents.models import ToolResult

            return ToolResult(ok=True, tool=self.name, data=[])

    run_id = uuid4()
    ctx = AgentContext(
        connection=None,
        tools=register_tools([FakeListFlags()]),
        run_id=run_id,
    )
    result = run_agent(EchoToolsAgent(), ctx, max_steps=4)
    assert result.finished is True
    assert result.agent_id == "echo_tools"
    assert result.run_id == run_id
    assert len(result.steps) == 2
    assert result.steps[0]["type"] == "call_tool"
    assert result.steps[1]["type"] == "finish"


def test_run_agent_stops_at_max_steps() -> None:
    class FakeListFlags:
        name = "list_open_flags"

        def run(self, ctx, args):
            from naijaledger.agents.models import ToolResult

            return ToolResult(ok=True, tool=self.name, data=[])

    ctx = AgentContext(
        connection=None,
        tools=register_tools([FakeListFlags()]),
        run_id=uuid4(),
    )
    result = run_agent(NeverFinishAgent(), ctx, max_steps=3)
    assert result.finished is False
    assert len(result.steps) == 3


def test_lookup_party_and_search_documents(db_connection) -> None:
    party = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Acme Retrieval Ltd"),
    )
    ctx = AgentContext(
        connection=db_connection,
        tools=register_tools(default_tools()),
        run_id=uuid4(),
    )
    by_id = LookupPartyTool().run(ctx, {"party_id": str(party.id)})
    assert by_id.ok is True
    assert by_id.data["canonical_name"] == "Acme Retrieval Ltd"

    by_name = LookupPartyTool().run(ctx, {"name": "Acme Retrieval"})
    assert by_name.ok is True
    assert any(row["id"] == party.id for row in by_name.data)

    docs = SearchDocumentsTool().run(ctx, {"query": "nonexistent-title-xyz"})
    assert docs.ok is True
    assert docs.data == []


def test_list_open_flags_tool(db_connection) -> None:
    ctx = AgentContext(
        connection=db_connection,
        tools=register_tools(default_tools()),
        run_id=uuid4(),
    )
    result = run_agent(EchoToolsAgent(), ctx, max_steps=4)
    assert result.finished is True
    assert result.steps[0]["result"]["ok"] is True

    # No publication path: review_decisions may not exist yet.
    exists = db_connection.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'review_decisions'
            """
        )
    ).scalar()
    if exists:
        assert db_connection.execute(text("SELECT count(*) FROM review_decisions")).scalar() == 0


def test_graph_neighbors_without_client() -> None:
    from naijaledger.agents.tools import GraphNeighborsTool

    ctx = AgentContext(
        connection=None,
        tools=register_tools([]),
        run_id=uuid4(),
        graph_client=None,
    )
    result = GraphNeighborsTool().run(ctx, {"node_id": "x", "label": "FinanceParty"})
    assert result.ok is False
    assert "not configured" in (result.error or "")


def test_graph_neighbors_unreachable_ok_false() -> None:
    if memgraph_reachable():
        return
    from naijaledger.agents.tools import GraphNeighborsTool
    from naijaledger.graph.client import MemgraphClient

    client = MemgraphClient.from_url("bolt://127.0.0.1:1")
    try:
        ctx = AgentContext(
            connection=None,
            tools=register_tools([]),
            run_id=uuid4(),
            graph_client=client,
        )
        result = GraphNeighborsTool().run(ctx, {"node_id": "x", "label": "FinanceParty"})
        assert result.ok is False
        assert result.error
    finally:
        client.close()
