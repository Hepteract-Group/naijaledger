# Spec 0022 — Human-review queue `review_decisions` (E8.3)

- **Epic / Issue**: E8.3 / #45
- **Status**: Implemented
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
    - Tests for CHECKs, transitions, gate helper; assert `approve_publish` rejects
      `reviewer` values starting with `agent:` or `system:` (human-only P3).
- **Out of scope**
  - Public API / admin UI for the queue (#102 later).
  - Actual public website publication pipeline (E9/E10).
  - Legal/FOI workflow (E12.4).

## 3. Design

### 3.1 Invariant

```text
enqueue (pending) ← agents/services
decide(approve_publish) ← human reviewer only (service-layer v1)
is_approved_for_publish ← true only if latest decided row is approve_publish
```

**v1 enforcement** is in `decide_review` (same class of guardrail as E6.2 human confirm —
no auth binding yet). The DB does not prevent a raw SQL insert of `approve_publish`;
application code and tests must. Follow-up: bind reviewer to authenticated session / DB role.

No `approve_publish` row may be created via `decide_review` with an agent-prefixed reviewer.

### 3.2 Lifecycle (update-in-place)

One **pending** row per subject at a time (partial unique index). Deciding **updates that
row** in place (`decision`, `reviewer`, `decided_at`, `rationale`). After decide, a new
`enqueue` may create a fresh pending row for the same subject. Not append-only history of
every event — decided rows remain as audit; only pending is unique/mutable.

### 3.3 Enqueue rules

- Subject for stories: `subject_type='story'`, `subject_id=story.id`.
- Require `VerificationReport.ok` to enqueue as `pending`.
- If not verified: do **not** create `approve_publish`; either skip or insert a **decided**
  row `needs_more_evidence` with `reviewer='system:verification'` (system may record
  non-publish outcomes only).

### 3.4 Decide rules

- Only from `pending`.
- **`approve_publish`** requires non-empty `reviewer` that does **not** start with `agent:`
  or `system:` (human-only — P3).
- `reject` / `needs_more_evidence` via `decide_review` also require non-empty `reviewer` not
  starting with `agent:` (humans or `system:` allowed for these two).
- After decide, new enqueue for same subject is allowed (no pending row remains).

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

- [x] Migration creates `review_decisions` with CHECKs and pending unique index.
- [x] Invalid decision / pending-with-reviewer fails CHECK.
- [x] `enqueue_review` creates pending; second pending for same subject fails unique.
- [x] `decide_review` to `approve_publish` with human reviewer succeeds; gate returns True.
- [x] `decide_review` with `reviewer` starting with `agent:` or `system:` raises for
      `approve_publish`.
- [x] `decide_review` with `reviewer='system:verification'` is allowed for
      `needs_more_evidence` only (not `approve_publish`).
- [x] `enqueue_story_for_review` with failed verification does not create `approve_publish`.
- [x] `is_approved_for_publish` is False when only pending/reject/needs_more_evidence exist.

## 6. Risks & mitigations

- **Agent spoofing reviewer** — naming convention is a **service-layer** guardrail only
  (mirrors E6.2 human-confirm pattern). Documented weakness; later auth binds reviewer to
  session / DB role. Not a DB CHECK in v1.
- **Multiple historical decisions** — gate uses latest decided row by `decided_at` (see §6
  rule below).

**v1 gate rule (explicit):** among rows with `decision <> 'pending'` for the subject, take
the one with max `decided_at`; approved iff that decision is `approve_publish`.

## 7. Open questions

None blocking.
