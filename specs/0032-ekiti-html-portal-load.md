# Spec 0032 — Ekiti HTML portal → finance load (vertical slice)

- **Epic / Issue**: ops / #147
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — first Explore fill from a seeded leaf portal.

## 1. Problem

Explore `/v1/parties` and `/v1/tenders` are empty until a leaf procurement source is
fetched and loaded. OCDS JSON normalizer exists; Ekiti publishes awards as a large HTML
table with OCIDs (not JSON packages).

## 2. Scope & non-scope

- **In scope**
  - Parse Ekiti `Home/Procurements` HTML table rows → OCDS release package.
  - Cap (`max_rows`) for first load.
  - Persist extraction + `load_normalized_release` with provenance.
  - CLI `naijaledger-portal-load` + `make portal-load-ekiti`.
  - Fixture tests (no live network in unit tests).
- **Out of scope**
  - Generic HTML extractor for all state portals.
  - NOCOPO per-row JSON downloads.
  - Budget Office PDF → `budget_lines` (#146).
  - Published claims / review gate.

## 3. Design

```text
scrapling fetch Ekiti HTML → archive document
  → ekiti_html_to_ocds_package(max_rows)
  → create_extraction(payload=package)
  → normalize_ocds_document → load_normalized_release
```

Column mapping (sampled 2026-07-11): title, entity, ocid, cost, contractor, award date.

## 4. Acceptance criteria

- [x] Fixture HTML yields ≥2 OCIDs → release package → normalized tenders/awards.
- [x] DB load upserts parties + tenders; re-load is idempotent on ocid.
- [x] CLI/make target documented.
- [x] Unit tests fixture-only.

## 5. Risks

- Portal layout drift breaks column indices — fixture + versioned `method_version`.
- 9MB HTML fetch timeout — scrapling timeout settings; cap rows on load.

## 6. Open questions

None blocking. Generalize to Adamawa/Kaduna as follow-ups.
