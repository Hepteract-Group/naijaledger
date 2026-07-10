# Spec 0020 — Agent runtime + retrieval tools (E8.1)

- **Epic / Issue**: E8.1 / #43
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — v1 is a **tool + runtime skeleton** with stub/deterministic
  agents; live LLM orchestration stays opt-in (same pattern as E6.2). Agents **propose only**
  (P3); no writes to `review_decisions` / no publication.

## 1. Problem

E5–E7 land canonical facts, graph projection, and anomaly flags. E8 needs a shared **agent
runtime** and **retrieval tool interfaces** so narrative/verification (E8.2) and other agents
can query Postgres + Memgraph (+ lightweight search) without each inventing ad-hoc I/O
(`SYSTEM_DESIGN.md` §4.10).

## 2. Scope & non-scope

- **In scope**
  - `naijaledger.agents` package: `Tool` protocol, `ToolResult` / `Citation`, `ToolRegistry`,
    `AgentContext`, `run_agent` loop (max steps, tool-call transcript).
  - Retrieval tools (read-only):
    - `lookup_party` — by id or name substring (Postgres).
    - `lookup_flag` / `list_open_flags` — wrap `anomaly.service.get_flag` /
      `list_open_flags`.
    - `search_documents` — Postgres `ILIKE` on `documents.title` (and optionally
      `sha256` prefix); v1 search stand-in (no `url` column on `documents` — URL lives on
      sources/fetch_records; OpenSearch/pgvector deferred).
    - `graph_neighbors` — 1-hop neighbors from Memgraph for a finance node id (optional if
      Memgraph unreachable; tool returns structured error, does not crash the run).
  - One **smoke agent** (`echo_tools`) that calls a fixed tool sequence for wiring tests.
  - Unit tests with fake tools / in-memory context; DB tests for Postgres tools; Memgraph tool
    skipped unless reachable (same pattern as graph rebuild tests).
- **Out of scope**
  - Narrative / verification agents (E8.2).
  - `review_decisions` table + human queue (E8.3).
  - Live LLM planner / ReAct with external APIs (follow-up; env-gated later).
  - Vector index / OpenSearch deployment.
  - Writing flags, merging parties, or any mutating tool in v1.

## 3. Design

### 3.1 Invariant

```text
Agent run → ToolResult[] + optional AgentDraft[]
  → NEVER insert review_decisions
  → NEVER auto-publish claims
```

Tools are **read-only**. Side-effecting actions remain explicit service calls outside the
runtime (human-gated elsewhere).

### 3.2 Run loop (v1)

```text
ctx = AgentContext(connection, graph_client?, tools, run_id)
agent.step(ctx, history) → AgentAction
  AgentAction = CallTool(name, args) | Finish(drafts?, summary)
until Finish or max_steps
```

Deterministic agents implement `step(ctx, history) -> AgentAction` (no LLM). A future LLM
agent can implement the same protocol behind an env flag.

### 3.3 Citations

Every `ToolResult` may include `citations: list[Citation]` with
`{kind, subject_type?, subject_id?, document_id?, label, detail?}`. Downstream E8.2 must be
able to attach evidence without re-querying blindly.

### 3.4 Search v1

`search_documents(query, limit=20)` uses parameterized SQL `ILIKE` against
`documents.title` (and optional exact/prefix match on `sha256`). Document as **interim**
until FTS/OpenSearch; do not pretend semantic search. Do not invent a `documents.url`
column — join to `sources` only if a later story needs URL search.

### 3.5 Graph tool safety

`graph_neighbors` only interpolates **code-constant** labels/rel types (same rule as
`MemgraphClient`). Node `id` is a bound parameter. On connection failure →
`ToolResult(ok=False, error=...)`.

## 4. Data contracts / schemas

No new tables in E8.1 (runs are ephemeral / returned to caller). Optional later:
`agent_runs` audit table.

```python
class Citation(BaseModel):
    kind: str  # party|flag|document|graph_edge|...
    subject_type: str | None = None
    subject_id: UUID | None = None
    document_id: UUID | None = None
    label: str
    detail: dict[str, Any] | None = None

class ToolResult(BaseModel):
    ok: bool
    tool: str
    data: Any = None
    error: str | None = None
    citations: list[Citation] = []

class Tool(Protocol):
    name: str
    def run(self, ctx: AgentContext, args: dict[str, Any]) -> ToolResult: ...

class ToolRegistry(BaseModel):
    tools: dict[str, Tool]  # name → tool; constructed via register_tools(list[Tool])

class AgentContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    connection: Connection
    tools: ToolRegistry
    run_id: UUID
    graph_client: GraphClient | None = None

class AgentAction(BaseModel):
    type: Literal["call_tool", "finish"]
    tool: str | None = None
    args: dict[str, Any] = {}
    summary: str | None = None
    drafts: list[dict[str, Any]] = []  # opaque for E8.2; unused by smoke

class Agent(Protocol):
    id: str
    def step(self, ctx: AgentContext, history: list[dict[str, Any]]) -> AgentAction: ...

class AgentRunResult(BaseModel):
    run_id: UUID
    agent_id: str
    steps: list[dict[str, Any]]  # transcript
    finished: bool
    summary: str | None
    drafts: list[dict[str, Any]]

def run_agent(
    agent: Agent,
    ctx: AgentContext,
    *,
    max_steps: int = 8,
) -> AgentRunResult: ...

def default_tools() -> list[Tool]: ...  # production retrieval set
```
## 5. Acceptance criteria (testable)

- [x] `run_agent` with smoke agent + fake tool completes with `finished=True` and a transcript.
- [x] `run_agent` stops at `max_steps` without hanging when the agent never finishes.
- [x] `lookup_party` / `list_open_flags` / `search_documents` return `ToolResult` against a
      migrated DB (empty ok; seeded when needed).
- [x] `default_tools()` names are unique and exclude mutating operations.
- [x] Smoke/agent run does not insert into `review_decisions` (table may not exist — assert no
      write attempt / zero rows if table exists).
- [x] `graph_neighbors` either returns neighbors or `ok=False` when Memgraph is down (no
      uncaught exception from `run_agent`).
- [x] Package is functional (Protocol + functions; Pydantic models only as needed).

## 6. Risks & mitigations

- **Tool sprawl** — keep v1 to the five retrieval tools above; E8.2 adds claim-check tools.
- **Search quality** — ILIKE is weak; documented interim; vector/OpenSearch is a follow-up issue.
- **Graph optional** — CI must not require Memgraph for the default suite.

## 7. Open questions

None blocking. LLM planner design deferred with E8.2 / opt-in env (mirror #114).
