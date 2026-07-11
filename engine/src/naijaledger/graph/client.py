"""Memgraph / Bolt graph client (E6.4)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any, Protocol

from neo4j import Driver, GraphDatabase

from naijaledger.graph.plan import GraphNode, GraphPlan, GraphRel

DEFAULT_MEMGRAPH_URL = "bolt://localhost:7687"
_FINANCE_LABELS = (
    "Agency",
    "Company",
    "Person",
    "FinanceParty",
    "Tender",
    "Award",
    "Contract",
)


class GraphClient(Protocol):
    def wipe_finance_projection(self) -> None: ...

    def apply_plan(self, plan: GraphPlan) -> None: ...

    def rebuild_from_plan(self, plan: GraphPlan) -> None: ...

    def count_nodes(self, labels: Sequence[str] | None = None) -> int: ...

    def close(self) -> None: ...


class MemgraphClient:
    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    @property
    def driver(self) -> Driver:
        return self._driver

    @classmethod
    def from_url(cls, url: str | None = None) -> MemgraphClient:
        resolved = (
            url
            or os.environ.get("MEMGRAPH_URL")
            or os.environ.get("MEMGRAPH_URI")
            or DEFAULT_MEMGRAPH_URL
        )
        driver = GraphDatabase.driver(resolved, auth=None)
        return cls(driver)

    def close(self) -> None:
        self._driver.close()

    def wipe_finance_projection(self) -> None:
        # Labels are code constants only — never interpolate user/DB strings into Cypher.
        with self._driver.session() as session:
            for label in _FINANCE_LABELS:
                session.run(f"MATCH (n:{label}) DETACH DELETE n")

    def apply_plan(self, plan: GraphPlan) -> None:
        with self._driver.session() as session:
            for node in plan.nodes:
                _create_node(session, node)
            for rel in plan.relationships:
                _create_rel(session, rel)

    def rebuild_from_plan(self, plan: GraphPlan) -> None:
        """Wipe + apply in one write transaction so a mid-failure rolls back."""

        def _work(tx: Any) -> None:
            for label in _FINANCE_LABELS:
                tx.run(f"MATCH (n:{label}) DETACH DELETE n")
            for node in plan.nodes:
                labels = ":".join(node.labels)
                tx.run(
                    f"MERGE (n:{labels} {{id: $id}}) SET n += $props",
                    id=node.properties["id"],
                    props=node.properties,
                )
            for rel in plan.relationships:
                tx.run(
                    f"""
                    MATCH (a:{rel.start_label} {{id: $start_id}})
                    MATCH (b:{rel.end_label} {{id: $end_id}})
                    MERGE (a)-[r:{rel.rel_type}]->(b)
                    SET r += $props
                    """,
                    start_id=str(rel.start_id),
                    end_id=str(rel.end_id),
                    props=rel.properties,
                )

        with self._driver.session() as session:
            session.execute_write(_work)

    def count_nodes(self, labels: Sequence[str] | None = None) -> int:
        target = labels or ("FinanceParty", "Tender", "Award", "Contract")
        total = 0
        with self._driver.session() as session:
            for label in target:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
                record = result.single()
                if record is not None:
                    total += int(record["c"])
        return total


def _create_node(session: Any, node: GraphNode) -> None:
    labels = ":".join(node.labels)
    session.run(
        f"MERGE (n:{labels} {{id: $id}}) SET n += $props",
        id=node.properties["id"],
        props=node.properties,
    )


def _create_rel(session: Any, rel: GraphRel) -> None:
    session.run(
        f"""
        MATCH (a:{rel.start_label} {{id: $start_id}})
        MATCH (b:{rel.end_label} {{id: $end_id}})
        MERGE (a)-[r:{rel.rel_type}]->(b)
        SET r += $props
        """,
        start_id=str(rel.start_id),
        end_id=str(rel.end_id),
        props=rel.properties,
    )


def memgraph_reachable(url: str | None = None) -> bool:
    client: MemgraphClient | None = None
    try:
        client = MemgraphClient.from_url(url)
        with client._driver.session() as session:
            session.run("RETURN 1")
        return True
    except Exception:
        return False
    finally:
        if client is not None:
            client.close()
