# Spec 0021 — Narrative + Verification agents (E8.2)

- **Epic / Issue**: E8.2 / #44
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — v1 agents are **deterministic / template-based** (no live LLM
  required for CI). They **propose** story drafts only (P3); enqueue to `review_decisions` is
  E8.3. Live LLM narrative remains a follow-up (env-gated, mirror #114).

## 1. Problem

E8.1 shipped the agent runtime and retrieval tools. Without a **narrative agent** (draft cited
stories from flags) and a **verification agent** (claim→evidence check), we cannot produce
reviewable drafts for human publication gating (`SYSTEM_DESIGN.md` §4.10; ROADMAP E8.2).

## 2. Scope & non-scope

- **In scope**
  - Pydantic models: `Claim`, `StoryDraft`, `VerificationFinding`, `VerificationReport`.
  - Pure `draft_story_from_flags(flags, citations?) -> StoryDraft` (template narrative from
    flag `evidence.summary` + subject ids).
  - `NarrativeAgent` (`Agent` protocol): uses `list_open_flags` (and optionally `lookup_flag` /
    `lookup_party`) then finishes with `drafts=[story.model_dump()]`.
  - Pure `verify_story(story: StoryDraft) -> VerificationReport`: every claim must have ≥1
    citation with resolvable `subject_id` or `document_id`; empty/missing citations → fail.
  - `VerificationAgent`: accepts a story in constructor/state (or reads last narrative draft
    from history); finishes with verification report in `drafts`.
  - Orchestrator helper: `propose_verified_story(ctx) -> ProposeResult` runs narrative then
    verification in-process (two `run_agent` calls or direct pure functions for tests).
  - Unit tests with synthetic flags; DB integration with seeded open flag optional.
- **Out of scope**
  - `review_decisions` table / enqueue / publish gate (E8.3).
  - Live LLM prose generation.
  - Public API / UI for stories.
  - Auto-publishing or writing flags.

## 3. Design

### 3.1 Invariant

```text
flags → StoryDraft (claims + citations)
     → VerificationReport (pass|fail per claim)
     → NEVER review_decisions / NEVER publish
```

A story that fails verification is still returned (with `ok=False`) so callers can inspect;
E8.3 will refuse to enqueue failed stories (or enqueue as `needs_more_evidence` — decided in
0022).

### 3.2 Claim shape

Each claim is a single checkable assertion:

```text
Claim(
  id, text,
  citations: list[Citation],  # from E8.1
  source_flag_id?: UUID,
  subject_type?, subject_id?
)
```

Narrative v1: one claim per open flag, `text` derived from
`"{rule} on {subject_type}/{subject_id}: {evidence.summary}"`, citation kind=`flag`.

Story body: short markdown joining claim texts (no rhetorical flourish required).

### 3.3 Verification rules (v1)

A claim **passes** iff:

1. `text` is non-empty, and
2. `citations` is non-empty, and
3. every citation has `label` non-empty and at least one of `subject_id` / `document_id` set.

Story **passes** iff all claims pass and there is ≥1 claim.

**v1 is structural citation hygiene only** — it does not resolve that the subject/document
exists in Postgres or that the claim text is true. Human review (E8.3) remains the
substantive gate. Optional later: existence checks against canonical tables.

### 3.4 Agents

| Agent | id | Behavior |
|-------|-----|----------|
| `NarrativeAgent` | `narrative` | step0: `list_open_flags`; step1: finish with story draft |
| `VerificationAgent` | `verification` | step0: finish with report for injected/prior story |

Prefer testing pure functions; agents are thin wrappers for runtime integration.

## 4. Data contracts / schemas

No new tables.

```python
class Claim(BaseModel):
    id: UUID
    text: str
    citations: list[Citation]
    source_flag_id: UUID | None = None
    subject_type: str | None = None
    subject_id: UUID | None = None

class StoryDraft(BaseModel):
    id: UUID
    title: str
    body: str
    claims: list[Claim]
    created_by: str  # agent id

class VerificationFinding(BaseModel):
    claim_id: UUID
    ok: bool
    reason: str

class VerificationReport(BaseModel):
    story_id: UUID
    ok: bool
    findings: list[VerificationFinding]

class ProposeResult(BaseModel):
    story: StoryDraft
    report: VerificationReport
    verified: bool  # alias of report.ok
```

## 5. Acceptance criteria (testable)

- [ ] `draft_story_from_flags` with ≥1 flag yields a story with matching claim count and
      non-empty citations.
- [ ] `draft_story_from_flags([])` yields a story with zero claims (or empty body) and
      verification fails.
- [ ] `verify_story` fails a claim with empty citations; passes a well-formed claim.
- [ ] `NarrativeAgent` via `run_agent` finishes with a `StoryDraft` in `drafts`.
- [ ] `VerificationAgent` / `propose_verified_story` returns `verified=True` for a seeded
      open flag with summary evidence.
- [ ] No writes to `review_decisions` (table may not exist).
- [ ] Functional code (pure draft/verify; Protocol agents).

## 6. Risks & mitigations

- **Template prose is dull** — acceptable for v1; LLM follow-up.
- **Structural verify ≠ truth** — E8.3 human gate remains; verification only checks citation
  hygiene.
- **Flag spam → long stories** — cap claims (e.g. 20) in draft helper.

## 7. Open questions

None blocking. Whether failed verification can still enqueue is E8.3 (`needs_more_evidence`).
