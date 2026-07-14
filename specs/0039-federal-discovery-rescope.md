# Spec 0039 — Federal discovery source re-scope (E2.3b)

- **Epic / Issue**: E2.3 follow-up / #82
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: yes — alternate **federal payments** source after
  Open Treasury retirement (tracked separately; does not block this re-scope).

## 1. Problem

Federal seeds still mix leaf extractors, PDF catalogs, thin discovery SPAs, and
interactive search UIs. Fetch/approve treats them alike, so OpenStates.ng and
CAC BOR burn schedule slots without producing finance rows. Follow-up to
`specs/0005-state-ocds-portal-audit.md`.

## 2. Scope & non-scope

- **In scope**
  - `ingest_role` on `sources` (registry metadata).
  - Seed catalog roles + auto-approve only roles that feed extract/load.
  - Demote OpenStates (discovery UI) and CAC BOR (search UI) to stay
    `proposed` (not scheduled).
  - Document NOCOPO as leaf + child-JSON follow-up.
  - File `needs-human` issue for federal payments alternate.
- **Out of scope**
  - Implementing NOCOPO per-row JSON downloads (file follow-up).
  - CAC PSC enrichment pipeline (stays #38 / E6.3).
  - BudgIT/OpenStates partnership ingest (stays #64 / E12.5).
  - Choosing the replacement payments portal.

## 3. Design

### Taxonomy (`ingest_role`)

| Role | Meaning | Seed auto-approve? |
|------|---------|--------------------|
| `leaf` | Page body has extractable rows (or JS leaf after Playwright) | Yes |
| `catalog` | Index of child PDF/XLSX/JSON; needs link-discovery | Yes |
| `discovery_ui` | Overview/aggregation SPA; no primary leaf for us | No — stay `proposed` |
| `search_ui` | Interactive lookup; no bulk dump | No — stay `proposed` |

### Federal decisions (2026-07-14)

| Source | Role | Status posture | Notes |
|--------|------|----------------|-------|
| NOCOPO `/Open-Data` | `leaf` | approved | Playwright table; child JSON downloads → follow-up issue |
| Budget Office docs | `catalog` | approved | Already link-discovered |
| NEITI documents | `catalog` | approved | Allowlist/filter later |
| OpenStates.ng | `discovery_ui` | **proposed** | No public leaf/API found; partnership path is #64 |
| CAC BOR | `search_ui` | **proposed** | Enrichment strategy = interactive API/search under #38 — not HTML scrape |
| Open Treasury | — | **retired** | Already retired; payments alternate is `needs-human` |

### Seed apply

`apply_seed_catalog` auto-approves only when `ingest_role ∈ {leaf, catalog}`.
Discovery/search roles remain `proposed`. Re-seed **demotes** previously
approved discovery/search federal URLs back to `proposed`.

## 4. Data contracts

```text
sources.ingest_role TEXT NOT NULL DEFAULT 'leaf'
  CHECK (ingest_role IN ('leaf','catalog','discovery_ui','search_ui'))
```

`SourceCreate.ingest_role` optional (default `leaf`).
`PublicSource.ingest_role` exposed on `/v1/sources`.

## 5. Acceptance criteria (testable)

- [x] Migration adds `ingest_role` with check constraint.
- [x] Seed catalog assigns roles; OpenStates + CAC stay `proposed` after seed.
- [x] Leaf/catalog seeds still auto-approve.
- [x] Spec documents CAC/OpenStates strategies and NOCOPO child-JSON gap.
- [x] `needs-human` issue opened for federal payments alternate.

## 6. Risks & mitigations

- **Lost schedule coverage** — intentional; empty archives waste ops time.
- **Public API additive field** — clients ignore unknown fields until typed.
- **Payments gap** — honesty over fiction; escalate human.

## 7. Open questions

- Which federal payments source replaces Open Treasury? → **needs-human**.
- OpenStates partnership data route? → deferred to #64.
