# Spec 0029 — Graph visualization (E10.4)

- **Epic / Issue**: E10.4 / #52
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — library choice recorded here: **react-force-graph-2d** for
  React-friendly force layout (ROADMAP lists Sigma.js / react-force-graph; stack table names
  Sigma for large graphs — follow-up if we outgrow force-graph). Live Memgraph HTTP deferred.

## 1. Problem

E6.4 projects finance into Memgraph, but the web has no graph surface. Progressive disclosure
needs a **relationship graph** after dashboards (`SYSTEM_DESIGN.md` §4.12). There is still no
public `/v1/graph` API (0023 out-of-scope).

## 2. Scope & non-scope

- **In scope**
  - Typed web graph document aligned with E6.4 labels (`Agency`/`Company`/`Person`/`Tender`/
    `Award`/`Contract` + rel types `ISSUED`/`AWARDED_TO`/…).
  - One **demo fixture** (clearly labelled) shaped like a small `GraphPlan`.
  - Route `/graph` + nav link; force-directed canvas via `react-force-graph-2d`.
  - Node click → detail panel (label, name/title, id); link to Explore.
  - Theme-aware node colors from design tokens (green/gold/indigo — not purple SaaS).
  - Pure helpers: `toForceGraphData`, `getDemoGraph`.
  - Tests: fixture shape, converter, `/graph` route renders (graph canvas mocked).
- **Out of scope**
  - `GET /v1/graph/*` / live Memgraph Bolt from the browser.
  - Sigma.js (follow-up for large graphs).
  - Editing, pathfinding UI, BO/`OWNED_BY` edges.
  - 3D graph (`react-force-graph-3d`).

## 3. Design

```text
/graph  → demo fixture → ForceGraph2D → node detail panel
         (banner: illustrative demo — not live Memgraph)
```

Later: swap fixture loader for `GET /v1/graph/subgraph` without changing the canvas contract.

## 4. Data contracts

```ts
type GraphNodeDoc = {
  id: string;
  labels: string[];
  name: string;
  kind: "party" | "tender" | "award" | "contract";
};

type GraphLinkDoc = {
  id: string;
  source: string;
  target: string;
  rel_type: string;
};

type GraphDocument = {
  id: string;
  title: string;
  demo: boolean;
  nodes: GraphNodeDoc[];
  links: GraphLinkDoc[];
};
```

## 5. Acceptance criteria (testable)

- [x] `/graph` renders title, demo banner, and a graph canvas region.
- [x] Fixture has ≥3 nodes and ≥2 links spanning party + tender (or award).
- [x] `toForceGraphData` maps nodes/links for the force-graph library.
- [x] Clicking a node shows a detail panel with name + labels.
- [x] Nav includes Graph.
- [x] `pnpm --filter @naijaledger/web lint typecheck test` pass.
- [x] No Memgraph / Bolt calls from the browser.

## 6. Risks & mitigations

- **Demo mistaken for live graph** — persistent demo banner.
- **Canvas in jsdom** — mock `react-force-graph-2d` in route tests.
- **Bundle size** — accept force-graph dep; code-split the canvas if needed.

## 7. Open questions

None blocking. Live graph API tracked as follow-up after this UI lands.
