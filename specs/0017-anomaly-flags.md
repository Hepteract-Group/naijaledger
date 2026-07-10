# Spec 0017 — Anomaly rule framework + `flags` (E7.1)

- **Epic / Issue**: E7.1 / #40
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — flags are hypotheses with evidence (P3); never auto-published
  claims. Rule list matches `data-model.md` / ROADMAP E7.2.

## 1. Problem

E5–E6 land canonical finance facts and a graph. Without a **rule framework** and persisted
`flags`, we cannot run red-flag detectors or attach evidence for human review
(`SYSTEM_DESIGN.md` §4.9).

## 2. Scope & non-scope

- **In scope**
  - Alembic migration: `flags` table (CHECKs, indexes).
  - Pure `AnomalyRule` protocol: `(ctx) -> list[FlagDraft]`.
  - `RuleContext` loaded from Postgres (read-only) for a run.
  - Persist helpers: `create_flag`, `list_open_flags`, `dismiss_flag` / `confirm_flag`
    (status transitions only — no publication).
  - Registry + `run_rules(connection, rule_ids | all) -> RunResult`.
  - One **smoke rule** (`_smoke_always_empty`) or fixture-only rule in tests proving the
    pipeline; real detectors are E7.2.
- **Out of scope**
  - Concrete red-flag logic (E7.2).
  - Backtest/precision harness (E7.3).
  - Election `overvote` rule (E11).
  - Public API / UI for flags.
  - Auto-publish or narrative drafting (E8).

## 3. Design

### 3.1 Invariant

Flags are **hypotheses**. `created_by` records the rule id (and optional agent). Status
`confirmed` means a human agreed the pattern is interesting — **not** that a public claim may
be published (that remains `review_decisions` / E8.3).

### 3.2 Run flow

```text
load RuleContext (read PG)
  → for each registered rule: rule.evaluate(ctx) → FlagDraft[]
  → upsert/insert flags (dedupe: open flag with same rule+subject)
  → return counts
```

Dedupe key for v1: unique partial index on `(rule, subject_type, subject_id) WHERE status = 'open'`.
Re-runs refresh `evidence` / `severity` / `updated_at` on conflict.

### 3.3 Severity

`low | medium | high` — advisory ranking for review queues. Rules set severity; humans may
later dismiss.

## 4. Data contracts / schemas

### 4.1 `flags`

```
flags(
  id uuid pk,
  subject_type text not null,   -- tender|award|contract|party|payment|budget_line|...
  subject_id uuid not null,
  rule text not null,           -- see CHECK list below
  severity text not null,       -- low|medium|high
  evidence jsonb not null,      -- structured; must include "summary" text
  status text not null,         -- open|dismissed|confirmed
  created_by text not null,     -- rule id or agent id
  reviewed_by text null,
  reviewed_at timestamptz null,
  meta jsonb null,
  created_at, updated_at
)
```

Rule CHECK (finance v1 + reserved):
`single_bidder|short_window|threshold_hugging|repeat_winner|shared_address|price_outlier|budget_payment_mismatch|overvote|smoke`

(`smoke` is test-only; production registry omits it.)

### 4.2 Python

```python
class FlagDraft(BaseModel):
    subject_type: str
    subject_id: UUID
    rule: str
    severity: Literal["low", "medium", "high"]
    evidence: dict[str, Any]  # requires "summary"
    created_by: str

class AnomalyRule(Protocol):
    id: str
    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]: ...

def run_anomaly_rules(
    connection: Connection,
    *,
    rule_ids: list[str] | None = None,
) -> RunResult: ...
```

`RuleContext` holds in-memory snapshots (tenders, awards, contracts, parties, payments,
budget_lines, relationships) loaded once per run — keep v1 simple; no graph dependency
required for E7.1 (E7.2 may add optional Memgraph reads later).

## 5. Acceptance criteria (testable)

- [ ] Migration creates `flags` with CHECKs and open-dedupe unique index.
- [ ] Inserting invalid `rule` / `status` / `severity` fails CHECK.
- [ ] `create_flag` round-trips; duplicate open (rule, subject) upserts evidence.
- [ ] `dismiss_flag` / `confirm_flag` set status + `reviewed_by` / `reviewed_at`.
- [ ] `run_anomaly_rules` with empty registry or smoke rule returns without error and
      does not write public claims.
- [ ] Package is functional (Protocol + functions; no framework-required classes beyond
      Pydantic).

## 6. Risks & mitigations

- **False positives** — flags are hypotheses; E7.3 measures precision; humans dismiss.
- **Rule CHECK churn** — adding a rule requires a migration; acceptable for v1.
- **Large evidence jsonb** — keep evidence compact (ids, thresholds, counts); link subjects
  rather than embed documents.

## 7. Open questions

None blocking. Threshold constants for E7.2 live in rule modules / config, not this spec.
