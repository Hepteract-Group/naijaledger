# Spec 0001 — Source Registry schema

- **Epic / Issue**: E2.1 / (to be linked)
- **Status**: Draft (example — demonstrates the spec format)
- **Author**: architecture
- **Needs human decision?**: no (schema is derivable from design; seeding sources is a separate `needs-human` issue)

## 1. Problem
NaijaLedger must catalog every data source it ingests, monitor source health, and drive scheduled
capture. This is the backbone of the engine (see `SYSTEM_DESIGN.md` §4.1, `data-model.md` `sources`).
Without it we cannot schedule fetches, detect outages (the Open Treasury TLS lapse), or track
provenance back to an origin.

## 2. Scope & non-scope
- In scope: the `sources` table + migration, and the enums it depends on.
- Non-scope: CRUD service (E2.2), health monitor (E2.4), discovery agent (E2.5), seeding (E2.3).

## 3. Design
A single `sources` table in the canonical Postgres store, plus supporting enum types. Registry rows
are created either by humans or proposed by the discovery agent (`status = 'proposed'`) and require
human approval (`status = 'approved'`) before the scheduler will fetch them.

## 4. Data contracts / schemas
Enums: `jurisdiction (federal|state|lga)`, `source_category (budget|procurement|payments|company|
election|other)`, `fetch_method (http|scrapling|playwright|api|manual)`, `source_format (pdf|xlsx|
csv|json|html|image)`, `health_status (healthy|degraded|down|tls_expired|unknown)`,
`source_status (proposed|approved|retired)`.

`sources` columns per `data-model.md` (`id, name, jurisdiction, region, category, url, fetch_method,
format, expected_cadence, last_fetched_at, last_success_hash, schema_fingerprint, health_status,
reliability_score, status, added_by, approved_by, created_at, updated_at`).

Indexes: unique on `(url, format)`; btree on `status`, `category`, `health_status`.

## 5. Acceptance criteria (testable)
- [ ] Migration creates all enums and the `sources` table with the columns above.
- [ ] `url + format` uniqueness is enforced.
- [ ] `status` defaults to `proposed`; `reliability_score` defaults to `0`.
- [ ] Migration is reversible (down migration drops table + enums cleanly).
- [ ] A test inserts a row, violates the unique constraint, and asserts the failure.

## 6. Risks & mitigations
- Schema drift vs `data-model.md` → keep this spec and the doc in sync in the same PR.
- Over-indexing early → start with the indexes above; add on evidence.

## 7. Open questions
- None blocking. (Seeding real sources is deferred to E2.3, which is `needs-human`.)
