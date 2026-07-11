# Spec 0035 — Live state map aggregates

- **Epic / Issue**: E10.5 follow-up / #143
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — polygons deferred; tender-value proxy for
  “contract volume” documented honestly.

## 1. Problem

`/map` still uses demo fixture metrics (spec 0030). Users need live totals by state,
with the existing ColumnLayer UX and state facet (#151 / #161). ADM1 polygon GeoJSON
is not in-repo and is deferred.

## 2. Scope & non-scope

- **In scope**
  - `GET /v1/map/states` — one row per known state/FCT code with centroids + aggregates.
  - `contract_volume` = `SUM(tenders.value_amount)` where `state_code` matches (kobo).
  - `anomaly_density` = open `flags` on tenders in that state / tender count (0 when no tenders).
  - Optional `?year=` filter on `tenders.fiscal_year`.
  - Web: fetch live data; banner says live when API succeeds; fixture fallback offline.
  - Extrusion height scales relative to national max (works for demo ints and live kobo).
- **Out of scope**
  - ADM1 polygon GeoJSON / polygon extrusion (follow-up issue).
  - Aggregating contracts/awards/party flags by geo hops.
  - Memgraph.
  - Time animation.

## 3. Design

```text
Postgres tenders + open flags
  → GET /v1/map/states(?year=)
  → MapPage merges with known centroids
  → NigeriaMap ColumnLayer (focus facet unchanged)
```

Flags remain **hypotheses** — density is investigative signal, not verified wrongdoing.

## 4. Data contracts

```ts
type PublicMapState = {
  id: string;              // "LA"
  name: string;
  lat: number;
  lng: number;
  contract_volume: number; // sum tender value_amount (kobo), 0 if none
  tender_count: number;
  open_flag_count: number;
  anomaly_density: number; // open_flag_count / tender_count, else 0
};
```

Always returns all known state codes (zeros when no data).

## 5. Acceptance criteria

- [x] `GET /v1/map/states` returns ≥37 rows with codes matching `finance/geo.py`.
- [x] Tender inserts with `state_code` + `value_amount` raise that state’s `contract_volume`.
- [x] Open tender flags raise `open_flag_count` / `anomaly_density`.
- [x] MapPage prefers live API; demo banner when fallback.
- [x] Relative extrusion height still works for large kobo sums.
- [x] Tests cover API aggregates; web lint/typecheck/test pass.

## 6. Risks

- Empty DB → all zeros (honest; not demo fiction).
- “Contract volume” is tender value, not `contracts` table — documented in OpenAPI.

## 7. Open questions

None blocking. Polygon vendoring is a separate issue.
