# Spec 0014 — Party matching + `merged_into` (E6.1)

- **Epic / Issue**: E6.1 / #36
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — start with deterministic rules + simple probabilistic score;
  LLM adjudication is #37.

## 1. Problem

The same real-world company/agency/person appears under many strings across OCDS portals
("Acme Ltd", "ACME LIMITED", "Acme Ltd."). E5 upserts on `(party_type, lower(canonical_name))`
only — it does not merge near-duplicates or identifier matches. Without matching, the graph and
anomaly rules under-count repeat winners and shared parties.

Derives from `SYSTEM_DESIGN.md` §4.6 and `parties.merged_into_id` in `data-model.md`.

## 2. Scope & non-scope

- **In scope**
  - Pure matching functions: normalize name, deterministic candidate rules, probabilistic score.
  - `propose_party_matches(connection, party_id) → list[MatchCandidate]`.
  - `apply_party_merge(connection, survivor_id, merged_id)` setting `merged_into_id` (no hard
    delete); block merge if either already merged or types differ.
  - Resolve helper: `canonical_party_id(connection, party_id)` follows `merged_into_id` chain.
  - Unit tests for normalizer + scoring; DB tests for merge + resolve.
- **Out of scope**
  - LLM adjudication / human confirm UI (#37).
  - Auto-merge on schedule (ops later); this story ships **propose + apply** APIs only.
  - Rewriting FKs on tenders/awards to survivor (v1: readers use `canonical_party_id`; bulk
    rewrite is a follow-up issue if needed).
  - Beneficial-ownership edges (#38).
  - Neo4j projection (#39).

## 3. Design

### 3.1 Name normalization (deterministic)

```text
lower → strip → collapse whitespace → remove punctuation
→ strip corporate suffixes (ltd, limited, plc, nig, nigeria, co, company, &amp;, and)
→ collapse leftover spaces
```

Store normalized form only in memory for matching (no new column required in v1).

### 3.2 Deterministic rules (high confidence)

A pair is a **deterministic match** if same `party_type` and any of:

1. Exact equal `normalize(canonical_name)`.
2. Shared strong identifier: same non-empty value for keys in
   `identifiers` under `rc`, `cac`, `tin`, `ocds_id` (case-insensitive string compare), or nested
   `identifier.id` + `identifier.scheme` both equal.
3. One name is the other plus only a stripped suffix (covered by (1) after normalize).

Deterministic matches score `1.0` and reason `deterministic:<rule>`.

### 3.3 Probabilistic score (medium)

If not deterministic, score in `[0, 1)`:

- Token Jaccard on normalized name tokens (weight 0.7).
- Prefix/similarity bonus if one normalized string startswith the other and min length ≥ 6
  (weight 0.3).

Emit candidate if score ≥ `0.82` (tunable constant). Reason `probabilistic:jaccard`.

Do **not** auto-apply probabilistic matches in v1 — only return candidates for #37 / human.

### 3.4 Merge semantics

```text
apply_party_merge(survivor, merged):
  assert survivor.id != merged.id
  assert same party_type
  assert survivor.merged_into_id is null
  assert merged.merged_into_id is null
  merged.merged_into_id = survivor.id
  merge aliases (union), identifiers (shallow merge), updated_at
```

`canonical_party_id`: walk `merged_into_id` until null (cap depth 16; error on cycle).

Readers of finance FKs **should** resolve through this helper when presenting entities
(documentation only in this story; call-site sweep is follow-up).

## 4. Data contracts

```python
class MatchCandidate(BaseModel):
    left_id: UUID
    right_id: UUID
    score: float
    reason: str
    rule: Literal["deterministic", "probabilistic"]

def normalize_party_name(name: str) -> str: ...
def score_party_pair(left: Party, right: Party) -> MatchCandidate | None: ...
def propose_party_matches(
    connection: Connection,
    party_id: UUID,
    *,
    limit: int = 20,
) -> list[MatchCandidate]: ...
def apply_party_merge(
    connection: Connection,
    *,
    survivor_id: UUID,
    merged_id: UUID,
) -> Party: ...  # returns survivor
def canonical_party_id(connection: Connection, party_id: UUID) -> UUID: ...
```

Package: `naijaledger.finance.matching` (pure) + merge helpers in `naijaledger.finance.service`.

## 5. Acceptance criteria (testable)

- [ ] `normalize_party_name("A.B.C. Limited") == normalize_party_name("abc ltd")`.
- [ ] Shared `identifiers.rc` → deterministic candidate score 1.0.
- [ ] Near-duplicate names without shared id → probabilistic candidate with score ≥ 0.82 or none.
- [ ] `apply_party_merge` sets `merged_into_id`; second merge of same row raises.
- [ ] `canonical_party_id(merged)` returns survivor.
- [ ] `propose_party_matches` returns both deterministic and probabilistic hits from a small fixture
      set in Postgres.

## 6. Risks & mitigations

- **False merges** — v1 only auto-documents deterministic rules in tests; production apply is
  explicit API (no cron). Probabilistic never auto-applied.
- **FK drift** — unresolved FKs still point at merged rows; resolve helper + later rewrite job.
- **Suffix list incomplete** — extend via constant; add tests when new patterns appear.

## 7. Open questions

None blocking. Threshold `0.82` may be tuned after real NOCOPO samples (#37 can adjust).
