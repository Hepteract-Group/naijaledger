"""Read-only Memgraph subgraph helpers for the public graph API (spec 0036)."""

from __future__ import annotations

from typing import Any, Literal, Protocol

GraphNodeKind = Literal["party", "tender", "award", "contract"]

_DEFAULT_LIMIT = 80
_MAX_LIMIT = 200

_SEED_LABEL_FILTER = (
    "seed:Agency OR seed:Company OR seed:Person OR seed:Tender OR seed:Award OR seed:Contract"
)
_NODE_LABEL_FILTER = "n:Agency OR n:Company OR n:Person OR n:Tender OR n:Award OR n:Contract"
_NEIGHBOR_LABEL_FILTER = "m:Agency OR m:Company OR m:Person OR m:Tender OR m:Award OR m:Contract"


class BoltDriver(Protocol):
    def session(self) -> Any: ...


def clamp_subgraph_limit(limit: int | None) -> int:
    if limit is None:
        return _DEFAULT_LIMIT
    return max(1, min(int(limit), _MAX_LIMIT))


def kind_for_labels(labels: list[str]) -> GraphNodeKind | None:
    label_set = set(labels)
    if label_set & {"Agency", "Company", "Person", "FinanceParty"}:
        return "party"
    if "Tender" in label_set:
        return "tender"
    if "Award" in label_set:
        return "award"
    if "Contract" in label_set:
        return "contract"
    return None


def display_name_for_node(labels: list[str], props: dict[str, Any]) -> str:
    for key in ("name", "title", "status", "ocid"):
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    kind = kind_for_labels(labels)
    node_id = str(props.get("id", ""))
    short = node_id[:8] if node_id else "?"
    if kind == "award":
        return f"Award · {short}"
    if kind == "contract":
        return f"Contract · {short}"
    if kind == "tender":
        return f"Tender · {short}"
    if kind == "party":
        return f"Party · {short}"
    return short


def _node_props(node: Any) -> dict[str, Any]:
    if node is None:
        return {}
    try:
        return dict(node)
    except TypeError:
        return {key: node[key] for key in node.keys()}


def _node_labels(node: Any) -> list[str]:
    labels = getattr(node, "labels", None)
    if labels is None:
        return []
    return list(labels)


def public_node_from_bolt(node: Any) -> dict[str, Any] | None:
    props = _node_props(node)
    node_id = props.get("id")
    if node_id is None:
        return None
    labels = _node_labels(node)
    kind = kind_for_labels(labels)
    if kind is None:
        return None
    return {
        "id": str(node_id),
        "labels": labels,
        "name": display_name_for_node(labels, props),
        "kind": kind,
    }


def fetch_subgraph(
    driver: BoltDriver,
    *,
    seed_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return a GraphDocument-shaped dict from Memgraph.

    Raises on Bolt errors so callers can mark ``available: false``.
    """
    capped = clamp_subgraph_limit(limit)
    with driver.session() as session:
        if seed_id:
            nodes, links = _ego_subgraph(session, seed_id=seed_id, limit=capped)
            title = f"Neighborhood of {seed_id}"
            doc_id = f"live-{seed_id}"
        else:
            nodes, links = _sample_subgraph(session, limit=capped)
            title = "Live finance graph"
            doc_id = "live-sample"
    return {
        "id": doc_id,
        "title": title,
        "demo": False,
        "available": True,
        "nodes": nodes,
        "links": links,
    }


def unavailable_subgraph(*, seed_id: str | None = None) -> dict[str, Any]:
    return {
        "id": f"unavailable-{seed_id}" if seed_id else "unavailable",
        "title": "Memgraph unavailable",
        "demo": False,
        "available": False,
        "nodes": [],
        "links": [],
    }


def _sample_subgraph(
    session: Any,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = session.run(
        f"MATCH (n) WHERE {_NODE_LABEL_FILTER} RETURN n LIMIT $limit",
        limit=limit,
    )
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for record in result:
        public = public_node_from_bolt(record["n"])
        if public is not None:
            nodes_by_id[public["id"]] = public
    ids = list(nodes_by_id.keys())
    if not ids:
        return [], []
    rels = session.run(
        """
        MATCH (a)-[r]->(b)
        WHERE a.id IN $ids AND b.id IN $ids
        RETURN a.id AS source, b.id AS target, type(r) AS rel_type, id(r) AS rid
        LIMIT $rel_limit
        """,
        ids=ids,
        rel_limit=limit * 4,
    )
    return list(nodes_by_id.values()), _links_from_id_records(rels)


def _ego_subgraph(
    session: Any,
    *,
    seed_id: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = session.run(
        f"""
        MATCH (seed {{id: $id}})
        WHERE {_SEED_LABEL_FILTER}
        OPTIONAL MATCH (seed)-[r]-(m)
        WHERE m IS NULL OR ({_NEIGHBOR_LABEL_FILTER})
        RETURN seed, r, m,
               startNode(r) AS start_n, endNode(r) AS end_n,
               type(r) AS rel_type, id(r) AS rid
        LIMIT $limit
        """,
        id=seed_id,
        limit=limit,
    )
    nodes_by_id: dict[str, dict[str, Any]] = {}
    link_records: list[dict[str, Any]] = []
    for record in result:
        seed = public_node_from_bolt(record["seed"])
        if seed is not None:
            nodes_by_id[seed["id"]] = seed
        neighbor = record["m"]
        if neighbor is not None and record["r"] is not None:
            public_m = public_node_from_bolt(neighbor)
            if public_m is None:
                continue
            nodes_by_id[public_m["id"]] = public_m
            start = public_node_from_bolt(record["start_n"])
            end = public_node_from_bolt(record["end_n"])
            if start is None or end is None:
                continue
            link_records.append(
                {
                    "source": start["id"],
                    "target": end["id"],
                    "rel_type": record["rel_type"],
                    "rid": record["rid"],
                }
            )
    return list(nodes_by_id.values()), _links_from_id_records(link_records)


def _links_from_id_records(records: Any) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        source = str(record["source"])
        target = str(record["target"])
        rel_type = str(record["rel_type"])
        rid = record["rid"]
        link_id = f"{rel_type}:{source}:{target}:{rid}"
        if link_id in seen:
            continue
        seen.add(link_id)
        links.append(
            {
                "id": link_id,
                "source": source,
                "target": target,
                "rel_type": rel_type,
            }
        )
    return links
