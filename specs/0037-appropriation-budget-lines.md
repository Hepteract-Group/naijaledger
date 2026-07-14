# Spec 0037 — Appropriation PDF → budget_lines

- **Epic / Issue**: E4/E5 / #146
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — v1 uses Appropriation Act table heuristics;
  Bill vs Act selection is documented (prefer Act).

## 1. Problem

Budget Office catalog discovery archives Appropriation PDFs, and
`budget_lines` + `budget_payment_mismatch` already exist, but there is no
non-OCDS path from PDF tables → canonical rows. Without it the mismatch rule
and federal budget transparency stay empty.

## 2. Scope & non-scope

- **In scope**
  - Spec + vertical slice: Docling table extract → map → upsert `budget_lines`
    with provenance.
  - Adapter on Budget Office catalog source URL for `format=pdf`.
  - Field map: `fiscal_year`, agency (party upsert), `code`, `description`,
    `allocated_amount` (kobo), `jurisdiction=federal`.
  - Size gate: skip PDFs above `budget_pdf_max_bytes` (default 25 MiB).
  - Row cap via `normalize_load_max_rows`.
  - Pure table-grid mapper testable without live Docling/network.
  - Backfill: `normalize_load` on a PDF document when adapter applies
    (CLI / worker); enqueue for catalog PDF children is best-effort follow-up
    if not already wired.
- **Out of scope**
  - Explore UI for budget lines.
  - Processing full 100MB+ Acts in CI.
  - OCR Pass 2 / vision-LLM for scanned Acts.
  - State budgets; payments load; public `/v1/budget-lines` (follow-up).
  - Perfect MDA entity resolution beyond name upsert.

## 3. Design

```text
Budget Office PDF document (archived)
  → adapter budget-office-appropriation (load_kind=budget)
  → size gate
  → Docling tables (or frozen table grids in tests)
  → map rows → NormalizedBudgetLine
  → upsert_budget_line + provenance_edges (subject_type=budget_line)
```

Document class heuristic (ops): prefer title/path containing `appropriation`
and `act` over proposal/guidelines when selecting what to enqueue.

## 4. Data contracts

Natural key unchanged: `(fiscal_year, agency_id, code, jurisdiction)`.

```python
NormalizedBudgetLine(
  fiscal_year: int,
  agency_name: str,
  code: str,
  description: str | None,
  allocated_amount: int | None,  # kobo
  jurisdiction: Literal["federal"] = "federal",
  page: int | None = None,
)

AdapterSpec(..., load_kind: "ocds" | "budget" = "ocds")
```

Settings: `budget_pdf_max_bytes: int = 25_000_000`.

## 5. Acceptance criteria

- [x] Table-grid mapper produces budget lines from a fixture grid.
- [x] Upsert is idempotent on the natural key.
- [x] Provenance edge written for `subject_type=budget_line`.
- [x] Oversize PDF skips with a clear reason (not a hard crash).
- [x] `normalize_load` budget branch loads rows when adapter matches.
- [x] Lint / typecheck / tests pass for touched modules.

## 6. Risks

- Docling table quality varies by Act layout — v1 heuristics, bump
  `method_version` when mapping improves.
- Amounts published as naira → always convert with `amount_to_kobo`.
- Huge Acts — hard size skip until chunked/page-gated extract exists.

## 7. Open questions

- Whether Amendment Acts share the same mapper (treat as same adapter for now).
- Public read API for budget lines — follow-up story.
