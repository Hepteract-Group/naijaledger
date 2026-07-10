"""Read-only retrieval tools (E8.1)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from naijaledger.agents.models import AgentContext, Citation, ToolResult
from naijaledger.anomaly.service import FlagNotFoundError, get_flag, list_open_flags
from naijaledger.finance.service import PartyNotFoundError, get_party


def _as_limit(value: Any, default: int = 20) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, 200))


class LookupPartyTool:
    name = "lookup_party"

    def run(self, ctx: AgentContext, args: dict[str, Any]) -> ToolResult:
        party_id_raw = args.get("party_id")
        name_query = args.get("name")
        if party_id_raw:
            try:
                party_id = UUID(str(party_id_raw))
            except (TypeError, ValueError):
                return ToolResult(ok=False, tool=self.name, error="invalid party_id")
            try:
                party = get_party(ctx.connection, party_id)
            except PartyNotFoundError:
                return ToolResult(ok=False, tool=self.name, error="party not found")
            return ToolResult(
                ok=True,
                tool=self.name,
                data=party.model_dump(mode="json"),
                citations=[
                    Citation(
                        kind="party",
                        subject_type="party",
                        subject_id=party.id,
                        label=party.canonical_name,
                    )
                ],
            )

        if not isinstance(name_query, str) or not name_query.strip():
            return ToolResult(
                ok=False,
                tool=self.name,
                error="provide party_id or non-empty name",
            )

        rows = ctx.connection.execute(
            text(
                """
                SELECT id, party_type, canonical_name, merged_into_id
                FROM parties
                WHERE merged_into_id IS NULL
                  AND canonical_name ILIKE :pattern
                ORDER BY canonical_name
                LIMIT :limit
                """
            ),
            {"pattern": f"%{name_query.strip()}%", "limit": _as_limit(args.get("limit"), 20)},
        ).mappings()
        parties = [dict(row) for row in rows]
        citations = [
            Citation(
                kind="party",
                subject_type="party",
                subject_id=row["id"],
                label=row["canonical_name"],
            )
            for row in parties
        ]
        return ToolResult(ok=True, tool=self.name, data=parties, citations=citations)


class LookupFlagTool:
    name = "lookup_flag"

    def run(self, ctx: AgentContext, args: dict[str, Any]) -> ToolResult:
        try:
            flag_id = UUID(str(args.get("flag_id")))
        except (TypeError, ValueError):
            return ToolResult(ok=False, tool=self.name, error="invalid flag_id")
        try:
            flag = get_flag(ctx.connection, flag_id)
        except FlagNotFoundError:
            return ToolResult(ok=False, tool=self.name, error="flag not found")
        return ToolResult(
            ok=True,
            tool=self.name,
            data=flag.model_dump(mode="json"),
            citations=[
                Citation(
                    kind="flag",
                    subject_type=flag.subject_type,
                    subject_id=flag.subject_id,
                    label=flag.rule,
                    detail={"flag_id": str(flag.id), "status": flag.status},
                )
            ],
        )


class ListOpenFlagsTool:
    name = "list_open_flags"

    def run(self, ctx: AgentContext, args: dict[str, Any]) -> ToolResult:
        limit = _as_limit(args.get("limit"), 100)
        flags = list_open_flags(ctx.connection, limit=limit)
        return ToolResult(
            ok=True,
            tool=self.name,
            data=[flag.model_dump(mode="json") for flag in flags],
            citations=[
                Citation(
                    kind="flag",
                    subject_type=flag.subject_type,
                    subject_id=flag.subject_id,
                    label=flag.rule,
                    detail={"flag_id": str(flag.id)},
                )
                for flag in flags
            ],
        )


class SearchDocumentsTool:
    name = "search_documents"

    def run(self, ctx: AgentContext, args: dict[str, Any]) -> ToolResult:
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult(ok=False, tool=self.name, error="query required")
        limit = _as_limit(args.get("limit"), 20)
        q = query.strip()
        rows = ctx.connection.execute(
            text(
                """
                SELECT id, source_id, title, sha256, format, archive_key
                FROM documents
                WHERE title ILIKE :pattern
                   OR sha256 LIKE :sha_prefix
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {
                "pattern": f"%{q}%",
                "sha_prefix": f"{q.lower()}%",
                "limit": limit,
            },
        ).mappings()
        docs = [dict(row) for row in rows]
        citations = [
            Citation(
                kind="document",
                document_id=row["id"],
                label=row["title"] or row["sha256"][:12],
            )
            for row in docs
        ]
        return ToolResult(ok=True, tool=self.name, data=docs, citations=citations)


_ALLOWED_NODE_LABELS = frozenset(
    {"Agency", "Company", "Person", "FinanceParty", "Tender", "Award", "Contract"}
)


class GraphNeighborsTool:
    name = "graph_neighbors"

    def run(self, ctx: AgentContext, args: dict[str, Any]) -> ToolResult:
        if ctx.graph_client is None:
            return ToolResult(ok=False, tool=self.name, error="graph client not configured")
        node_id = args.get("node_id")
        if not isinstance(node_id, str) or not node_id.strip():
            return ToolResult(ok=False, tool=self.name, error="node_id required")
        label = args.get("label") or "FinanceParty"
        if label not in _ALLOWED_NODE_LABELS:
            return ToolResult(ok=False, tool=self.name, error=f"label not allowed: {label}")

        try:
            neighbors = _query_neighbors(ctx.graph_client, label, node_id.strip())
        except Exception as exc:  # noqa: BLE001 — tool must not crash the run
            return ToolResult(ok=False, tool=self.name, error=str(exc))

        return ToolResult(
            ok=True,
            tool=self.name,
            data=neighbors,
            citations=[
                Citation(
                    kind="graph_edge",
                    label=f"{item.get('rel_type')}→{item.get('neighbor_id')}",
                    detail=item,
                )
                for item in neighbors
            ],
        )


def _query_neighbors(graph_client: Any, label: str, node_id: str) -> list[dict[str, Any]]:
    # Labels are code-constant only (validated against allowlist).
    driver = getattr(graph_client, "_driver", None)
    if driver is None:
        raise RuntimeError("graph client has no Bolt driver")
    cypher = (
        f"MATCH (n:{label} {{id: $id}})-[r]-(m) "
        "RETURN type(r) AS rel_type, m.id AS neighbor_id, labels(m) AS neighbor_labels "
        "LIMIT 50"
    )
    with driver.session() as session:
        result = session.run(cypher, id=node_id)
        return [
            {
                "rel_type": record["rel_type"],
                "neighbor_id": record["neighbor_id"],
                "neighbor_labels": list(record["neighbor_labels"] or []),
            }
            for record in result
        ]


def default_tools() -> list[Any]:
    return [
        LookupPartyTool(),
        LookupFlagTool(),
        ListOpenFlagsTool(),
        SearchDocumentsTool(),
        GraphNeighborsTool(),
    ]
