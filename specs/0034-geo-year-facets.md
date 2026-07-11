# Spec 0034 — State / LGA / year facets (Explore, Sources, Map, Graph)

- **Epic / Issue**: E10 follow-up / #151
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — free-text LGA + ISO-ish state codes for v1; full ADM2
  reference table is a follow-up.

## 1. Problem

Users cannot drill by **state**, **LGA**, or **year**. Tenders lack geo/time columns; Explore
only filters parties by `q` / type; Sources ignore `region` in the UI; Map/Graph cannot sync
to the same facet model.

## 2. Scope & non-scope

- **In scope**
  - Canonical columns on `tenders`: `state_code`, `lga`, `fiscal_year` (nullable).
  - Populate from portal adapters (Ekiti: year + location columns; default state from source).
  - Public API: filter tenders + sources by `state` / `lga` / `year`; `GET /v1/facets` for
    distinct values + known state list.
  - Shared web facet controls (URL params `state`, `lga`, `year`) on Explore (tenders),
    Sources, Map (demo ranking filter), Graph (demo label filter when applicable).
  - Honest empty: unknown LGA/year stay null; no invented LGAs.
- **Out of scope**
  - Official ADM2 LGA gazetteer table / validation.
  - Filtering parties/flags by geo join (follow-up).
  - Live map/graph aggregates (#143 / #141).
  - Election PU hierarchy (E11).

## 3. Design

```text
Adapter → NormalizedTender.{state_code,lga,fiscal_year}
  → tenders columns
  → GET /v1/tenders?state=&lga=&year=
  → GET /v1/sources?state=   (sources.region matched via state name/code)
  → GET /v1/facets
  → FacetBar (URL-serializable)
```

`state_code`: two-letter codes aligned with map fixtures (`EK`, `LA`, `FC`, …).
`lga`: trimmed free text from portal (e.g. `ADO-EKITI`); filter uses `ILIKE`.
`fiscal_year`: integer from portal year column when parseable.

## 4. Data contracts

```sql
ALTER TABLE tenders ADD state_code text NULL;
ALTER TABLE tenders ADD lga text NULL;
ALTER TABLE tenders ADD fiscal_year integer NULL;
-- indexes: state_code, fiscal_year, lower(lga)
```

```ts
// URL facets
?state=EK&lga=ADO-EKITI&year=2026
```

## 5. Acceptance criteria

- [x] Migration adds tender geo/year columns + indexes.
- [x] Ekiti adapter populates state_code/lga/fiscal_year on load.
- [x] `/v1/tenders` filters by state, lga, year; `/v1/sources` by state (region).
- [x] `/v1/facets` returns states + years (+ lgas when present).
- [x] Optional `?state=` scopes `lgas` to that `state_code` (#158).
- [x] Explore tenders + Sources use FacetBar; Map filters ranking by state; URL round-trips.
- [x] Map year facet refetches live aggregates (complete 4-digit years only).
- [x] Tests cover API filters + Ekiti year/location parse.

## 6. Risks

- Free-text LGA drift across portals — document as best-effort until ADM2.
- Existing rows null until re-normalize (bump Ekiti `method_version`).

## 7. Open questions

None blocking. ADM2 seed is a follow-up issue.
