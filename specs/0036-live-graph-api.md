# Spec 0036 — Live Memgraph graph read API

- **Epic / Issue**: E10.4 follow-up / #141
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — no user Cypher; geo hop filter deferred
  (projection has no state props).

## 1. Problem

`/graph` is fixture-only (spec 0029). Without a public read API over the E6.4
Memgraph projection, the page cannot leave demo mode.

## 2. Scope & non-scope

- **In scope**
  - `GET /v1/graph/subgraph` — read-only bounded subgraph shaped as
    `GraphDocument` (web canvas contract).
  - Optional `seed_id` (ego 1-hop) and `limit` (hard-capped).
  - Soft degrade when Memgraph is unreachable (`available: false`).
  - Web: prefer live API; demo fixture fallback when unavailable / fetch error.
  - Allowlisted labels only; no client-supplied Cypher.
- **Out of scope**
  - Geo/year filtering in Memgraph (no geo props on projection; facet still
    seeds search text only).
  - Write routes, full-graph dump, Sigma.js scale-up.
  - Separate `/neighbors` HTTP (UI uses subgraph links).
  - Browser → Bolt.

## 3. Design

```text
Memgraph finance projection (spec 0016)
  → GET /v1/graph/subgraph(?seed_id=&limit=)
  → GraphPage → toForceGraphData (unchanged)
```

Unavailable: HTTP 200 with `available: false`, empty nodes/links — web falls
back to demo (same honesty pattern as map offline).

Empty-but-reachable projection: `available: true`, empty nodes — web shows
live empty state (not demo fiction).

## 4. Data contracts

```ts
type PublicGraphNode = {
  id: string;
  labels: string[];
  name: string;   // name | title | status | kind+short id
  kind: "party" | "tender" | "award" | "contract";
};

type PublicGraphLink = {
  id: string;
  source: string;
  target: string;
  rel_type: string;  // directed as stored (e.g. FROM_AWARD: Contract→Award)
};

type PublicGraphDocument = {
  id: string;
  title: string;
  demo: false;
  available: boolean;
  nodes: PublicGraphNode[];
  links: PublicGraphLink[];
};
```

Query: `seed_id?: string`, `limit?: int` (default 80, max 200).

## 5. Acceptance criteria

- [x] `GET /v1/graph/subgraph` returns `PublicGraphDocument` without needing Postgres.
- [x] Fake/unreachable client → `available: false`, empty nodes/links, HTTP 200.
- [x] Seeded fake driver with nodes+edges → correct kinds, names, directed links.
- [x] Rejects / ignores client Cypher (no such param).
- [x] GraphPage prefers live when `available` and non-empty; demo on error/`available: false`.
- [x] Live empty projection shows non-demo empty banner (not illustrative fixture).
- [x] Engine + web lint/typecheck/tests pass.

## 6. Risks

- Large projections truncated by `limit` — documented; seed_id for focus.
- Award nodes lack display names in projection — synthesized labels.
- `FROM_AWARD` direction differs from demo fixture — canvas treats links as undirected for UX.

## 7. Open questions

None blocking. Geo-aware subgraph seeds (Postgres → Memgraph expand) is a follow-up.
