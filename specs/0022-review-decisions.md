# Spec 0022 — Human-review queue `review_decisions` (E8.3)

- **Epic / Issue**: E8.3 / #45
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — schema matches `data-model.md`; only humans may
  `approve_publish` (P3). Agents/services may enqueue pending items and never auto-approve.

## 1. Problem

E8.2 produces verified story drafts. Without a persisted **`review_decisions`** queue and
publication gate, nothing enforces P3 (“AI proposes, humans dispose”) before public claims
(`SYSTEM_DESIGN.md` §4.10 / §2 P3; ROADMAP E8.3).

## 2. Scope & non-scope

- **In scope**
  - Alembic migration: `review_decisions` table with CHECKs + indexes.
  - Service functions: `enqueue_review`, `list_pending_reviews`, `get_review_decision`,
    `decide_review` (`approve_publish` | `reject` | `needs_more_evidence`).
  - Gate helper: `is_approved_for_publish(connection, subject_type, subject_id) -> bool`.
  - Integration with E8.2: `enqueue_story_for_review(connection, story, report)` enqueues only
    when `report.ok` (verified); otherwise returns error / optional
    `needs_more_evidence` decision without approve path.
  - Tests for CHECKs, transitions, gate helper; assert agents cannot call decide with
    machine identity for `approve_publish` without `reviewed_by` human id (require non-empty
    `reviewer` that is not an agent id prefix — simple rule: `reviewer` must not start with
    `agent:`).
- **Out of scope**
  - Public API / admin UI for the queue (#102 later).
  - Actual public website publication pipeline (E9/E10).
  - Legal/FOI workflow (E12.4).

## 3. Design

### 3.1 Invariant

```text
enqueue (pending) ← agents/services
decide(approve_publish) ← human reviewer only
is_approved_for_publish ← true only if latest decision is approve_publish
```

No row with `decision=approve_publish` may be inserted by an agent id.

### 3.2 Status model

v1 uses **one row per decision event** (append-only style), not a mutable status column:

```text
review_decisions(
  id, subject_type, subject_id,
  decision,  -- pending|approve_publish|reject|needs_more_evidence
  reviewer,  -- null while pending; required when decided
  rationale,
  decided_at,  -- null while pending
  meta jsonb,  -- may store story_id, verification snapshot
  created_at, updated_at
)
```

`pending` rows are the queue. Deciding updates the same row (set decision, reviewer,
decided_at) — simpler for unique open queue:

Unique partial index: `(subject_type, subject_id) WHERE decision = 'pending'`.

### 3.3 Enqueue rules

- Subject for stories: `subject_type='story'`, `subject_id=story.id`.
- Require `VerificationReport.ok` to enqueue as `pending`.
- If not verified: do **not** create `approve_publish`; either skip or insert
  `needs_more_evidence` with `reviewer='system:verification'` (allowed — not approve).

### 3.4 Decide rules

- Only from `pending`.
- `approve_publish` / `reject` / `needs_more_evidence` require non-empty `reviewer` not
  starting with `agent:`.
- Sticky: after decide, new enqueue for same subject creates a new pending only if no
  pending exists (unique index).

## 4. Data contracts / schemas

```sql
review_decisions (
  id uuid pk default gen_random_uuid(),
  subject_type text not null,
  subject_id uuid not null,
  decision text not null check (
    decision in ('pending','approve_publish','reject','needs_more_evidence')
  ),
  reviewer text null,
  rationale text null,
  decided_at timestamptz null,
  meta jsonb null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (decision = 'pending' and reviewer is null and decided_at is null)
    or (decision <> 'pending' and reviewer is not null and decided_at is not null)
  )
);
-- unique pending (subject_type, subject_id)
```

```python
def enqueue_review(...) -> ReviewDecision: ...
def decide_review(..., decision: Literal["approve_publish","reject","needs_more_evidence"],
                  reviewer: str, rationale: str | None) -> ReviewDecision: ...
def is_approved_for_publish(connection, subject_type, subject_id) -> bool: ...
def enqueue_story_for_review(connection, story, report) -> ReviewDecision: ...
```

## 5. Acceptance criteria (testable)

- [ ] Migration creates `review_decisions` with CHECKs and pending unique index.
- [ ] Invalid decision / pending-with-reviewer fails CHECK.
- [ ] `enqueue_review` creates pending; second pending for same subject fails unique.
- [ ] `decide_review` to `approve_publish` with human reviewer succeeds; gate returns True.
- [ ] `decide_review` with `reviewer` starting with `agent:` raises for `approve_publish`.
- [ ] `enqueue_story_for_review` with failed verification does not create `approve_publish`.
- [ ] `is_approved_for_publish` is False when only pending/reject/needs_more_evidence exist.

## 6. Risks & mitigations

- **Agent spoofing reviewer** — naming convention is weak; later auth binds reviewer to
  session. Document as v1 guardrail.
- **Multiple historical decisions** — gate uses latest `approve_publish` if any, or
  “latest non-pending wins”: prefer **any** `approve_publish` that has not been superseded.
  v1 rule: `is_approved_for_publish` ↔ exists row with `decision='approve_publish'` for the
  subject (reject later does not auto-revoke unless we add revoke — for v1, **latest decided
  row by decided_at** wins).

**v1 gate rule (explicit):** among rows with `decision <> 'pending'` for the subject, take
the one with max `decided_at`; approved iff that decision is `approve_publish`.

## 7. Open questions

None blocking.
