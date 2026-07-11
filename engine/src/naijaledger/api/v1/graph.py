"""Public graph subgraph endpoint (spec 0036)."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from neo4j.exceptions import Neo4jError

from naijaledger.api.schemas import PublicGraphDocument, PublicGraphLink, PublicGraphNode
from naijaledger.graph.client import MemgraphClient
from naijaledger.graph.read import fetch_subgraph, unavailable_subgraph

logger = logging.getLogger(__name__)

router = APIRouter(tags=["graph"])

_GRAPH_DESCRIPTION = (
    "Bounded read-only subgraph from the Memgraph finance projection. "
    "No client Cypher. When Memgraph is unreachable, returns available=false "
    "with empty nodes/links (HTTP 200). Rel directions match the projection "
    "(e.g. FROM_AWARD is Contract→Award)."
)


def get_memgraph_client() -> Generator[MemgraphClient | None, None, None]:
    """Yield a live client, or None when Memgraph is unreachable."""
    client: MemgraphClient | None = None
    try:
        client = MemgraphClient.from_url()
        with client.driver.session() as session:
            session.run("RETURN 1")
    except Exception:
        if client is not None:
            client.close()
        yield None
        return
    try:
        yield client
    finally:
        client.close()


@router.get(
    "/graph/subgraph",
    response_model=PublicGraphDocument,
    summary="Bounded live finance subgraph",
    description=_GRAPH_DESCRIPTION,
)
def get_graph_subgraph(
    client: Annotated[MemgraphClient | None, Depends(get_memgraph_client)],
    seed_id: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> PublicGraphDocument:
    if client is None:
        return _to_document(unavailable_subgraph(seed_id=seed_id))
    try:
        raw = fetch_subgraph(client.driver, seed_id=seed_id, limit=limit)
    except Neo4jError:
        logger.exception("Memgraph subgraph query failed")
        return _to_document(unavailable_subgraph(seed_id=seed_id))
    return _to_document(raw)


def _to_document(raw: dict[str, Any]) -> PublicGraphDocument:
    return PublicGraphDocument(
        id=str(raw["id"]),
        title=str(raw["title"]),
        demo=bool(raw.get("demo", False)),
        available=bool(raw.get("available", True)),
        nodes=[PublicGraphNode(**node) for node in raw.get("nodes", [])],
        links=[PublicGraphLink(**link) for link in raw.get("links", [])],
    )
