# Spec 0009 — Extraction contract & dual-pass pipeline (E4)

- **Epic / Issue**: E4.1 / #27 (contract) — also seeds E4 stories (routing+Magika, confidence schema, Docling tables)
- **Status**: Approved (contract via #94); schema implementation in progress (#88)
- **Author**: agent
- **Needs human decision?**: no — contract approved; PDF-table engine decided (Docling in-engine, #29).

## 1. Problem

E3 archives raw bytes into MinIO and dedupes them into `documents`. Nothing yet turns those bytes
into structured facts. E4 must parse each `document` into rows in `extractions` (`data-model.md`
§`extractions`) with **provenance** (page/region) and an explicit **confidence signal**, so E5 can
normalize only what is trustworthy and E8.3 can gate the rest behind human review.

Two design principles shape this spec:

1. **Structure before semantics + confidence tagging.** Deterministic parsers (spreadsheets, JSON,
   PDF text-layer / layout tables) are exact and cheap — treat their output as high-confidence
   `extracted`. LLM/OCR/vision output is probabilistic — tag it `inferred` (with a score) or
   `ambiguous`, never silently mixed with deterministic facts.
2. **Detect the format, don't trust the label.** A `.pdf` extension or `Content-Type` header lies
   often enough (scanned images renamed to `.pdf`, HTML error pages served as `application/json`).
   Sniff the real content type up front and **quarantine** what we cannot classify, rather than
   feeding the wrong parser and emitting garbage.

This derives from `SYSTEM_DESIGN.md` (E4 Extraction) and the P2 "provenance always" prime directive.

## 2. Scope & non-scope

- **In scope**
  - The `extract_document` contract (functional signature + result shape) that every parser implements.
  - Content-type detection step (Magika-based) → parser routing → **quarantine** path for unknowns.
  - Deterministic Pass 1 parsers: XLSX/CSV, JSON, PDF text/layout tables via **Docling** (in-engine).
  - `extractions` schema additions: `method`/`method_version`, `derivation` tier
    (`extracted|inferred|ambiguous`), `confidence`, and per-block provenance into `provenance_edges`.
- **Non-scope (own stories)**
  - The actual OCR/vision Pass-2 implementation (E4.5 / #31) — this spec only defines how its output
    is tagged (`inferred`/`ambiguous`) and gated.
  - OCDS normalization (E5) and claim-level confidence scoring for publication (separate E8 story).

## 3. Design

### 3.1 Pipeline

```
document (archived bytes + declared format)
  → 1. detect content type (Magika)          # sniff real type from bytes
      ├─ high-confidence + supported → route to Pass 1
      ├─ high-confidence + unsupported → skip (record, no error)
      └─ low-confidence / mismatch vs declared format → QUARANTINE (needs-human)
  → 2. Pass 1 — deterministic (structure)
      ├─ xlsx/csv  → tabular rows            derivation=extracted, confidence=1.0
      ├─ json      → typed records           derivation=extracted, confidence=1.0
      └─ pdf       → text blocks + tables    derivation=extracted, confidence=1.0
                     (Docling layout + TableFormer; page + bbox provenance)
  → 3. Pass 2 — probabilistic (semantics)    # only when Pass 1 is empty/insufficient
      ├─ pdf(scanned) → OCR text/tables      derivation=inferred,  confidence∈[0,1)
      └─ vision-LLM (cost-gated, last resort) derivation=inferred/ambiguous
  → 4. write extractions (+ provenance_edges per block: page, region/bbox)
```

- **Deterministic-first is a hard rule.** Pass 2 runs only when Pass 1 yields nothing usable for a
  document (e.g. a scanned PDF with no recoverable layout). We never "upgrade" a deterministic
  result with an LLM guess. This keeps the cheap, exact, auditable path dominant and reserves
  spend/risk for the genuinely unstructured tail.
- **Quarantine, don't guess.** When Magika's top label is low-confidence, or contradicts the
  `documents.format` we inferred at fetch time (spec 0006), the document is parked in a quarantine
  state and surfaced for human triage instead of being force-parsed — refuse rather than emit
  misleading output.

### 3.2 Confidence tiering (derivation)

| derivation  | meaning                                   | source                              | default confidence |
|-------------|-------------------------------------------|-------------------------------------|--------------------|
| `extracted` | exact, reproducible, no model judgement   | spreadsheet/JSON/Docling PDF parse  | `1.0`              |
| `inferred`  | model-derived, may be wrong               | OCR, vision-LLM                     | model score `[0,1)`|
| `ambiguous` | conflicting or below-threshold signal     | Pass-2 with low agreement/context   | `< threshold`      |

`derivation` + `confidence` travel with each extraction and propagate onto `provenance_edges`, so any
downstream fact records *how* it was obtained. E5 normalizes `extracted` freely; `inferred`/`ambiguous`
facts require an E8.3 human `review_decisions` gate before they can back a public claim (P3).

### 3.3 Contract (functional)

Every parser is a pure-ish function of `(document, bytes) → ExtractionOutcome`; all I/O (MinIO read,
DB write) stays at the edges, per the functional-code rule.

### 3.4 PDF tables — Docling in-engine (decided)

Procurement PDFs are table-heavy. **Docling** (MIT; layout analysis + TableFormer) runs **inside**
`/engine` behind the same `extract_document` contract:

- Native page + bbox provenance maps cleanly onto `provenance_edges`.
- No external conversion service on the ingestion hot path (WORM locality, blast-radius, and
  Python runtime fit all favour in-process).
- Pin the Docling version; record it as `method_version` on each `extractions` row.
- When Docling finds no usable text/tables (likely scan), Pass 1 returns empty → Pass 2 (OCR)
  may run per E4.5.

## 4. Data contracts / schemas

### 4.1 `extractions` (extend existing table — `data-model.md` §`extractions`)

Current: `document_id, extractor (enum), extractor_version, ok bool, payload jsonb, ocr_used bool, created_at`.

Add / rename:

```
extractions(
  id                uuid pk,
  document_id       uuid  -> documents(id),
  method            text,          -- xlsx | csv | json | pdf_text | pdf_table | ocr | vision_llm
  method_version    text,          -- pinned lib/model version for reproducibility
  derivation        text,          -- extracted | inferred | ambiguous   (CHECK constraint)
  confidence        numeric(4,3),  -- 0.000..1.000; deterministic parsers = 1.000
  ok                boolean,
  payload           jsonb,         -- normalized block/table/record payload
  content_type      text,          -- Magika top label at parse time
  content_type_conf numeric(4,3),  -- Magika confidence
  status            text,          -- parsed | quarantined | unsupported | failed
  created_at        timestamptz
)
```

(`extractor`/`ocr_used` fold into `method`/`method_version`; `derivation` supersedes the implicit
trust model.)

### 4.2 `ExtractionOutcome` (Python, engine)

```python
class Block(TypedDict):
    kind: str                      # "table" | "text" | "record"
    payload: dict[str, Any]
    page: int | None
    region: dict[str, float] | None   # bbox {x0,y0,x1,y1} when known

class ExtractionOutcome(TypedDict):
    method: str
    method_version: str
    derivation: str                # extracted | inferred | ambiguous
    confidence: float
    status: str                    # parsed | quarantined | unsupported | failed
    content_type: str
    content_type_conf: float
    blocks: list[Block]

def extract_document(document: Document, data: bytes) -> ExtractionOutcome: ...
```

Each `Block` with a `page`/`region` yields one `provenance_edges` row
(`document_id, extraction_id, page, region, method`).

## 5. Acceptance criteria (testable)

- [x] Alembic migration adds `derivation` (CHECK in {extracted,inferred,ambiguous}), `confidence`,
      `method`/`method_version`, `content_type`, `content_type_conf`, `status` to `extractions`
      (and matching `derivation`/`confidence` on `provenance_edges`) — #88.
- [x] Magika detection returns `(label, confidence)`; a low-confidence or format-mismatched document
      produces `status="quarantined"` and **no** parsed rows (unit test with a mislabeled fixture)
      — #87.
- [x] XLSX and JSON fixtures parse via Pass 1 with `derivation="extracted"`, `confidence=1.0`
      (#30).
- [ ] A text-layer PDF fixture via Docling yields ≥1 table block with `page` + `region` provenance
      and `method`/`method_version` recording the pinned Docling version.
- [x] Pass 2 is not invoked when Pass 1 returns usable blocks (assert via spy/mock) (#28).
- [x] Every emitted block with page/region writes a matching `provenance_edges` row (#28).
- [ ] A scanned-PDF fixture (no recoverable layout) routes to Pass 2 and is tagged `inferred`
      (not `extracted`).

## 6. Risks & mitigations

- **Magika dependency weight / false negatives** — it is a small ONNX model (not a large LLM); pin the
  version, treat *low confidence* as quarantine (fail-safe), and keep the fetch-time format
  (spec 0006) as a cross-check rather than sole authority.
- **Docling weight / cold start** — pin version; isolate behind the `extract_document` boundary so
  the rest of Pass 1 (xlsx/json) stays light; record `method_version` for reproducibility.
- **Confidence inflation** — deterministic parsers hard-code `1.0`; models may only ever emit `< 1.0`
  (enforced), so an LLM guess can never masquerade as an exact extraction.
- **Quarantine backlog** — surface a count/queue; a growing quarantine is a signal to add a parser or
  fix source classification, not to loosen the guard.
- **Schema churn** — `payload` stays `jsonb` so block shapes can evolve without migrations.

## 7. Open questions

- **Vision-LLM cost gating** — per-document budget + only-on-quarantine trigger (E4.5).
- **PII / local vs hosted models** — scanned election forms may carry PII; prefer local OCR/models
  for those source categories (ties to security-and-privacy rule).
