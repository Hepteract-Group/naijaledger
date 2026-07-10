# Spec 0013 — Provenance subjects on canonical finance rows (E5.3)

- **Epic / Issue**: E5.3 / #34
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — `provenance_edges.subject_*` already exist; wire them at
  normalize/load time.

## 1. Problem

E4 writes `provenance_edges` for extraction blocks (page/region) with **null** `subject_type` /
`subject_id`. E5.2 loads tenders/awards/contracts/parties but does not link those rows back to
`document_id` + `extraction_id`. Without that link, “every datum → document+region” (P4 /
`SYSTEM_DESIGN`) is incomplete for the canonical store.

## 2. Scope & non-scope

- **In scope**
  - Optional `ProvenanceContext` on `load_normalized_release` (document_id, extraction_id,
    method, derivation, confidence, optional page/region).
  - Create one `provenance_edges` row per loaded subject (`party` / `tender` / `award` /
    `contract`) with `subject_type` + `subject_id` set.
  - `list_provenance_edges_for_subject(connection, subject_type, subject_id)` helper.
  - Tests: load with context → edges queryable by subject.
- **Out of scope**
  - Backfilling historical edges.
  - HTML/non-OCDS adapters.
  - Human `verified_by` / review gate (E8).
  - Award/contract upsert idempotency (#35) — re-load may create duplicate edges until then;
    document and accept for v1, or skip edge insert when identical subject+extraction already
    exists (prefer skip-duplicate).

## 3. Design

```text
normalize_ocds_release → load_normalized_release(conn, release, provenance=ctx?)
                              │
                              ├─ upsert parties / tender / insert awards / contracts
                              └─ for each new/updated subject id:
                                   create_provenance_edge(subject_type, subject_id, …ctx)
```

Idempotency for edges: unique logical key
`(extraction_id, subject_type, subject_id)` — if a row exists, do not insert another
(no migration required if we SELECT-then-INSERT).

## 4. Data contracts

```python
class ProvenanceContext(BaseModel):
    document_id: UUID
    extraction_id: UUID
    method: ExtractionMethod  # or str compatible with edges.method
    derivation: ExtractionDerivation
    confidence: float
    page: int | None = None
    region: dict[str, float] | None = None

def load_normalized_release(
    connection: Connection,
    release: NormalizedRelease,
    *,
    provenance: ProvenanceContext | None = None,
) -> LoadResult: ...

def list_provenance_edges_for_subject(
    connection: Connection,
    subject_type: str,
    subject_id: UUID,
) -> list[ProvenanceEdge]: ...
```

`LoadResult` gains `provenance_edge_ids: list[UUID]`.

Subject type strings (v1): `party`, `tender`, `award`, `contract`.

## 5. Acceptance criteria (testable)

- [x] Loading a fixture release **with** provenance creates edges for tender + parties +
      award + contract with correct `subject_*`.
- [x] Loading **without** provenance creates zero new provenance edges (backward compatible).
- [x] Second load with same extraction+subjects does not duplicate edges.
- [x] `list_provenance_edges_for_subject` returns the tender edge after load.

## 6. Risks & mitigations

- **Duplicate awards on re-load** — mitigated in the same change set by upserting awards on
  `(tender_id, supplier_id, meta.ocds_award_id)` and contracts on
  `(agency_id, supplier_id, meta.ocds_contract_id)` (closes #35 for the OCDS path).
- **method on edges** may be `json` from extraction while finance load is “normalize” —
  store the **extraction** method from context (evidence method), not a new enum value.

## 7. Open questions

None blocking.
