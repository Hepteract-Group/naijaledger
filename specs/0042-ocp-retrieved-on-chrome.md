# Spec 0042 — OCP archive retrieval date on public amounts

- **Epic / Issue**: E5 / #206
- **Status**: Approved
- **Author**: agent
- **Needs human decision?**: no — publication rule decided in spec 0041 §7.2 (founder 2026-10-10).

## 1. Problem

OCP Data Registry archive tenders store `meta.ocp_retrieved_on` and `meta.source_kind=ocp_registry` (spec 0041 / #203). Public API and Explore strip `meta`, so readers see amounts with no archive date and can treat 2021–2025 totals as current spend.

## 2. Scope & non-scope

- **In scope**
  - Optional public field `ocp_retrieved_on` (ISO date string) on tender, award, and contract read DTOs and partner export of those resources.
  - Populate it only when that row’s amount comes from `source_kind=ocp_registry` (else `null`).
  - Explore: show the date next to tender amounts (table, compare, detail).
  - Map state aggregates: when a state’s tender sum includes archive rows, expose a retrieval footnote (`ocp_retrieved_on_min` / `ocp_retrieved_on_max` + archive tender count) and render it on Map.
  - Unit tests: OCP fixture payload includes the date; live/non-OCP rows leave it null; full `meta` stays absent from public JSON.
- **Out of scope**
  - Re-deciding whether archive rows may appear (0041 §7.2).
  - Exposing full `meta` or other provenance keys.
  - Changing the loader’s storage of the field.
  - Graph / stories / distribution charts (they do not show live OCP amounts today).

## 3. Design

```text
public DTO gains optional ocp_retrieved_on
  tender:  CASE WHEN meta->>'source_kind' = 'ocp_registry'
                 THEN meta->>'ocp_retrieved_on' ELSE NULL
  award:   JOIN tenders; same CASE on award.meta, date from tender.meta
  contract: JOIN awards → tenders (or tender via award); CASE on contract.meta

map /v1/map/states per state_code:
  ocp_archive_tender_count
  ocp_retrieved_on_min / ocp_retrieved_on_max
    (only over tenders with source_kind=ocp_registry)

UI:
  format amount + " · as of YYYY-MM-DD" when date present
  map: if archive count > 0, footnote "archive as of DATE" or "as of MIN–MAX"
```

Do not invent a date when missing: leave `ocp_retrieved_on` null (amount still shown; operator debt to re-load).

## 4. Data contracts / schemas

```text
PublicTender.ocp_retrieved_on: str | None   # "YYYY-MM-DD"
PublicAward.ocp_retrieved_on: str | None
PublicContract.ocp_retrieved_on: str | None

PublicMapState:
  ocp_archive_tender_count: int              # default 0
  ocp_retrieved_on_min: str | None
  ocp_retrieved_on_max: str | None
```

Full `meta` remains private. Partner export uses the same DTOs.

## 5. Acceptance criteria (testable)

- [ ] Public tender list/detail JSON for a row with `source_kind=ocp_registry` and `ocp_retrieved_on` includes that ISO date; `"meta"` is still absent.
- [ ] Public award/contract detail for an OCP-linked row includes `ocp_retrieved_on` from the parent tender; live_portal / non-OCP rows have `null`.
- [ ] Explore shows the retrieval date next to the tender amount when the field is set.
- [ ] `GET /v1/map/states` for a state whose tenders are (mostly) OCP archive includes archive count and min/max retrieval dates; Map UI shows an “as of” footnote when count > 0.
- [ ] Non-OCP tenders and map states with zero archive tenders leave the new fields null/0.

## 6. Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Amount shown without date if meta incomplete | Fail open on amount; null date (no invented value) |
| Map mixes live + archive | Footnote whenever `ocp_archive_tender_count > 0` |

## 7. Open questions

None.
