# Spec 0015 — LLM match adjudication + human confirm (E6.2)

- **Epic / Issue**: E6.2 / #37
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — LLM is advisory only; merges require explicit human confirm.
  Provider choice is pluggable (stub default; optional live LLM behind env).

## 1. Problem

E6.1 proposes probabilistic matches but never auto-merges them. Hard near-duplicates still need a
judgment call. `SYSTEM_DESIGN.md` §4.6 / agent roles call for an **entity-resolution agent** that
adjudicates hard matches with **human confirmation** before `merged_into_id` is set.

Without a persisted proposal + confirm path, operators cannot review LLM opinions, and agents
must not silently call `apply_party_merge` on probabilistic pairs.

## 2. Scope & non-scope

- **In scope**
  - Table `party_match_proposals` (pending / confirmed / rejected / withdrawn).
  - Pluggable `MatchAdjudicator` protocol: input pair + E6.1 candidate → opinion
    (`same_entity` | `different` | `uncertain`) + rationale + model id.
  - Default **stub adjudicator** (deterministic heuristic, no network) for tests/CI.
  - Optional live LLM adjudicator behind env (`NAIJALEDGER_MATCH_ADJUDICATOR=llm` + API key);
    never required for CI.
  - Service: `create_proposal_from_candidate`, `list_pending_proposals`,
    `confirm_proposal` → `apply_party_merge`, `reject_proposal`.
  - **Invariant**: `confirm_proposal` is the only path from a proposal to merge; LLM never
    calls merge directly.
- **Out of scope**
  - Admin UI for the queue (#102 later).
  - Auto-confirm / cron auto-merge.
  - Deterministic matches auto-merge policy (still explicit apply; optional follow-up).
  - Beneficial ownership (#38), Neo4j (#39).
  - Publication `review_decisions` (E8.3) — different subject.

## 3. Design

### 3.1 Flow

```text
propose_party_matches (E6.1)
        │ probabilistic (and optionally deterministic)
        ▼
adjudicate(pair) → AdjudicationOpinion
        │
        ▼
INSERT party_match_proposals (status=pending)
        │
        ▼
human confirm / reject  (API/CLI now; admin UI later)
        │
   confirm ──► apply_party_merge(survivor, merged)
   reject  ──► status=rejected
```

### 3.2 Survivor selection

Default: lower `created_at` wins as survivor (stable). Opinion may suggest swap; human confirm
passes explicit `survivor_id` / `merged_id` (must be the two party ids on the proposal).

### 3.3 Stub vs LLM

| Mode | Behaviour |
|---|---|
| `stub` (default) | If E6.1 score ≥ 0.95 → `same_entity`; elif score ≥ 0.82 → `uncertain`; else `different`. Rationale cites score. |
| `llm` | Prompt with both party records (name, aliases, identifiers, type). Parse structured JSON opinion. On parse/API failure → `uncertain` + error in rationale; **never** merge. |

Cost gate: live LLM only when env enabled; batch size left to caller.

### 3.4 Human confirm

`confirm_proposal(connection, proposal_id, *, confirmed_by: str, survivor_id, merged_id)`:
- proposal must be `pending`
- ids must match proposal’s two parties
- calls `apply_party_merge`
- sets proposal `status=confirmed`, `resolved_at`, `resolved_by`

Reject sets `rejected` without merge.

## 4. Data contracts / schemas

### 4.1 `party_match_proposals`

```
party_match_proposals(
  id uuid pk,
  left_party_id uuid not null references parties(id) restrict,
  right_party_id uuid not null references parties(id) restrict,
  match_score numeric(4,3) not null,
  match_rule text not null,          -- deterministic | probabilistic
  match_reason text not null,
  opinion text not null,             -- same_entity | different | uncertain
  opinion_rationale text not null,
  adjudicator text not null,         -- stub | llm:<model>
  status text not null,              -- pending | confirmed | rejected | withdrawn
  suggested_survivor_id uuid null references parties(id),
  resolved_by text null,
  resolved_at timestamptz null,
  meta jsonb null,
  created_at, updated_at,
  CHECK (left_party_id <> right_party_id),
  CHECK (opinion IN (...)),
  CHECK (status IN (...)),
  CHECK (match_rule IN ('deterministic','probabilistic'))
)
```

Unique partial index: one **pending** row per unordered pair
`(least(left,right), greatest(left,right)) WHERE status = 'pending'`.

### 4.2 Python

```python
class AdjudicationOpinion(BaseModel):
    opinion: Literal["same_entity", "different", "uncertain"]
    rationale: str
    adjudicator: str
    suggested_survivor_id: UUID | None = None

class MatchAdjudicator(Protocol):
    def adjudicate(
        self, left: Party, right: Party, candidate: MatchCandidate
    ) -> AdjudicationOpinion: ...

def create_match_proposal(...) -> PartyMatchProposal: ...
def list_pending_match_proposals(connection, *, limit=50) -> list[PartyMatchProposal]: ...
def confirm_match_proposal(connection, proposal_id, *, confirmed_by, survivor_id, merged_id) -> Party: ...
def reject_match_proposal(connection, proposal_id, *, rejected_by: str) -> PartyMatchProposal: ...
```

## 5. Acceptance criteria (testable)

- [ ] Migration creates `party_match_proposals` with CHECKs and pending-pair unique index.
- [ ] Stub adjudicator returns `uncertain` for mid-band probabilistic scores.
- [ ] Creating a proposal persists opinion + leaves parties unmerged.
- [ ] `confirm_match_proposal` merges via `apply_party_merge` and sets status `confirmed`.
- [ ] `reject_match_proposal` does not merge; status `rejected`.
- [ ] Second pending proposal for the same pair fails unique constraint.
- [ ] Live LLM path is not required for CI (stub default).

## 6. Risks & mitigations

- **LLM hallucination / over-merge** — human confirm required; default opinion `uncertain` on
  failure.
- **Provider lock-in** — Protocol + env switch; stub is CI source of truth.
- **Queue without UI** — list/confirm/reject service is enough for agents/CLI until #102.

## 7. Open questions

None blocking. Optional later: auto-open proposals for all probabilistic hits above threshold on
a schedule (jobs kind).
