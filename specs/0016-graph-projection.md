# Spec 0016 — Graph projection builder (E6.4)

- **Epic / Issue**: E6.4 / #39
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — graph engine is **Memgraph** (SYSTEM_DESIGN open Q #1 /
  docker-compose). Projection is rebuildable from Postgres (P6).

## 1. Problem

Canonical finance facts live in Postgres. Relationship queries (repeat winners, shared
suppliers, agency→contract→company) need a graph projection. Without a rebuildable projector,
Neo4j/Memgraph drifts from the source of truth.

Derives from `SYSTEM_DESIGN.md` §4.8 and ROADMAP E6.4.

## 2. Scope & non-scope

- **In scope**
  - Pure builders: Postgres rows → Cypher-oriented graph ops (nodes/edges).
  - Memgraph client wrapper (Bolt) with explicit connection URL from env
    (`MEMGRAPH_URL`, default `bolt://localhost:7687`).
  - `rebuild_finance_graph(connection, graph)` — wipe projection labels for finance domain,
    reload parties (canonical only), tenders, awards, contracts + relationships.
  - Idempotent rebuild (safe to re-run).
  - Tests: unit tests on builders without Memgraph; optional integration test skipped unless
    `MEMGRAPH_URL` is reachable.
- **Out of scope**
  - Beneficial-ownership edges (#38, blocked on access).
  - Payments / budget_lines projection (follow-up).
  - Real-time incremental sync (batch rebuild is v1).
  - Public graph API / Sigma UI (E10.4).
  - Switching to Neo4j Community or AGE (not needed; Memgraph decided).

## 3. Design

### 3.1 Labels & relationships

| Postgres | Graph |
|---|---|
| `parties` (`agency`) | `(:Agency {id, name, party_type})` |
| `parties` (`company`) | `(:Company {id, name, party_type})` |
| `parties` (`person`) | `(:Person {id, name, party_type})` |
| `tenders` | `(:Tender {id, ocid, title})` |
| `awards` | `(:Award {id})` |
| `contracts` | `(:Contract {id, status})` |

Edges (using canonical party ids via `canonical_party_id` / skip if `merged_into_id` set — only
project **unmerged** parties; FKs resolve through `canonical_party_id`):

```text
(Agency)-[:ISSUED]->(Tender)
(Tender)-[:RESULTED_IN]->(Award)
(Award)-[:AWARDED_TO]->(Company|Person)
(Contract)-[:FROM_AWARD]->(Award)          # when award_id set
(Agency)-[:CONTRACTED]->(Contract)
(Company|Person)-[:SUPPLIED]->(Contract)
```

### 3.2 Rebuild algorithm

1. Delete all nodes with label in finance set (DETACH DELETE) — projection-only; never touch PG.
2. Upsert/create nodes from PG SELECT.
3. Create relationships by id.
4. Return counts `{nodes, relationships}`.

Functional core: `plan_finance_projection(parties, tenders, awards, contracts) -> list[GraphOp]`
where `GraphOp` is create_node / create_rel. Executor applies ops via Bolt.

### 3.3 Merged parties

Do not create nodes for parties with `merged_into_id IS NOT NULL`. When an award/contract FK
points at a merged party, resolve with `canonical_party_id` before emitting edges.

## 4. Data contracts

```python
class GraphNode(BaseModel):
    labels: list[str]
    key: str          # "id"
    properties: dict[str, Any]

class GraphRel(BaseModel):
    rel_type: str
    start_label: str
    start_id: UUID
    end_label: str
    end_id: UUID
    properties: dict[str, Any] = {}

class GraphPlan(BaseModel):
    nodes: list[GraphNode]
    relationships: list[GraphRel]

def plan_finance_projection(...) -> GraphPlan: ...
def rebuild_finance_graph(pg: Connection, graph: GraphClient) -> RebuildStats: ...
```

Package: `naijaledger.graph` (plan + memgraph client).

## 5. Acceptance criteria (testable)

- [ ] `plan_finance_projection` emits Agency/Company nodes and ISSUED / AWARDED_TO edges for a
      fixture set (no Memgraph required).
- [ ] Merged parties are omitted; FKs resolve to survivor id in the plan.
- [ ] `rebuild_finance_graph` against Memgraph (when available) is idempotent: second rebuild
      yields same node count.
- [ ] Without Memgraph, integration test skips cleanly.
- [ ] No Postgres writes from the graph package.

## 6. Risks & mitigations

- **Full wipe on rebuild** — acceptable for v1; document downtime for large graphs.
- **Memgraph Cypher dialect quirks** — keep queries simple; pin image in compose.
- **UUID property types** — store as string in graph properties.

## 7. Open questions

None blocking. Follow-ups: payments projection; incremental sync; BO edges after #38.
