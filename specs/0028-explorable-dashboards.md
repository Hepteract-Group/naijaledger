# Spec 0028 — Explorable dashboards + source drill-down (E10.3)

- **Epic / Issue**: E10.3 / #51
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — frontend over existing E9 `/v1` reads; archive-byte
  download remains deferred (0023). Charts: lightweight SVG distribution for v1 (ECharts when
  series get richer — follow-up).

## 1. Problem

Progressive disclosure needs an **explorable dashboard** after narratives: filter/sort/compare
canonical entities and drill to the **source registry** (`SYSTEM_DESIGN.md` §4.12). Explore is
still a flat parties list; Sources is a placeholder.

## 2. Scope & non-scope

- **In scope**
  - Explore dashboard over public reads: **parties**, **tenders**, **flags** (hypotheses).
  - Filters: parties (`party_type`, `q` via API); tenders/flags client-side on the loaded page
    (title/rule text, severity/method when present).
  - Sort: client-side on loaded rows (name/title, value, severity, updated).
  - Compare: select up to **2** rows → side-by-side field panel.
  - Distribution chart (SVG) for the active resource (party_type / method / severity counts).
  - Row → detail panel (inline) with key fields + link toward Sources.
  - Sources: `/sources` list from `GET /v1/sources`; `/sources/:id` detail drill-down.
  - Flags UI copy: clearly **hypotheses**, not verified claims.
  - Tests: sort/filter helpers; Explore renders filters; Sources list/detail (mocked fetch).
- **Out of scope**
  - ECharts / Observable Plot / maps / graph (E10.4–E10.5; richer charts follow-up).
  - MinIO archive bytes / signed URLs (0023 follow-up).
  - Awards/contracts list UI (API is id-get only).
  - Server-side sort/filter for tenders/flags (API unchanged).
  - Auth, admin, story publication (#137 / #126).

## 3. Design

### 3.1 Routes

| Path | Page |
|------|------|
| `/explore` | Dashboard (resource switcher + table + chart + compare) |
| `/sources` | Source registry list |
| `/sources/:id` | Source detail |

### 3.2 Explore layout

One job: explore data. Controls (resource, filters, sort) → table → optional compare strip.
Distribution chart sits beside or above the table (not a hero clutter strip of unrelated stats).

URL search params optional for shareable state: `resource`, `q`, `party_type`, `sort`.

### 3.3 Source drill-down

Sources list → detail shows registry fields (name, url, jurisdiction, category, format,
health, status, cadence). No document bytes. Explore detail panel links to `/sources`.

## 4. Data contracts / schemas

Reuse E9 public DTOs. Web clients:

```ts
fetchParties({ party_type?, q?, limit?, offset? })
fetchTenders({ limit?, offset? })
fetchFlags({ limit? })
fetchSources({ status?, limit?, offset? })
fetchSource(id)
```

Pure helpers: `sortRows`, `filterTenders`, `filterFlags`, `countBy`, `toggleCompareSelection`
(max 2).

## 5. Acceptance criteria (testable)

- [x] Explore switches among parties / tenders / flags and loads via `/v1`.
- [x] Parties support type + name filter (API query params).
- [x] Client-side sort changes row order for the active resource.
- [x] Selecting two rows shows a compare panel with both labels.
- [x] Flags surface hypothesis wording (not “verified”).
- [x] `/sources` lists sources (or empty/error); `/sources/:id` shows detail or not-found.
- [x] Distribution chart renders counts for the active dataset (including empty → no bars).
- [x] `pnpm --filter @naijaledger/web lint typecheck test` pass.
- [x] No new chart library dependency in this story.

## 6. Risks & mitigations

- **Empty DB** — empty states + Status/engine hint (same as E10.1).
- **Flags misread as facts** — persistent hypothesis label on Flags tab/detail.
- **Large pages** — keep `limit` ≤ 50 default; no fake total counts.

## 7. Open questions

None blocking. ECharts adoption tracked as follow-up when multi-series finance charts land.
