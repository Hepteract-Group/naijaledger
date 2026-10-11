# Spec 0040 — BudgIT GovSpend payments ingest

- **Epic / Issue**: E5 / #179 (decision recorded on #172, 2026-10-01)
- **Status**: Draft (awaiting founder decisions on licence gate and history loss)
- **Author**: agent
- **Needs human decision?**: yes — see §8 (Founder decisions needed)

## 1. Problem

Open Treasury is unreachable (expired TLS, request timeout) and is retired. Federal `payments` rows are empty, so `budget_payment_mismatch` cannot run on federal data. The 2026-10-01 spike (`docs/learnings/2026-10-01-federal-payments-sources.md`) found one public leaf: BudgIT GovSpend.

Probe of `GET https://app.govspend.ng/api/payments/?page=1` on 2026-10-01 returned HTTP 200, `Content-Type: application/json`, 100 rows, `last: 4680`, `next` pointing at page 2.

## 2. Scope & non-scope

- **In scope**
  - Seed one approved source: BudgIT GovSpend, `ingest_role=leaf`, `category=payments`, `fetch_method=api`, `format=json`.
  - Paginate the public JSON list, archive each page before parse, map rows into `payments` with provenance.
  - Credit BudgIT GovSpend on every loaded row.
  - Fixture tests. No live network in unit tests.
  - A CLI cap (`max_pages`, default 2) so the first run is a sample, not all ~468,000 rows.
- **Out of scope**
  - Sending email to BudgIT.
  - The download endpoints (`/api/payments/download/` returned 500; search-download returned 403/405/404). Do not call them.
  - Linking a payment to a `contracts` row.
  - Fuzzy match of payer names onto Budget Office agency names.
  - Federation Account Allocation Committee monthly PDFs.
  - A Freedom of Information request to the Office of the Accountant-General of the Federation.
  - Re-opening Open Treasury.

## 3. Design

```text
GET https://app.govspend.ng/api/payments/?page=N
  → archive page bytes + fetch_record (before parse)
  → parse_govspend_page
  → SAVEPOINT page_N
  → create_extraction(method=json)
  → upsert parties + payments (skip rows whose content_hash hasn't changed)
  → provenance_edges (append-only per extraction)
  → COMMIT page
  → on failure: ROLLBACK TO SAVEPOINT, write failed extraction, continue
  → follow `next` until null, empty page, or max_pages
```

**Transaction isolation**: One savepoint per page. On parse or load failure, roll back to the savepoint, write a failed extraction record with the error, and continue to the next page. Commit page by page so partial runs are resumable. Reuse the OCP per-page transaction size cap pattern.

`make fetch-sources` walks `http`, `scrapling`, and `playwright` only. This source uses `fetch_method=api` so that walker skips it. Loading is a dedicated command, same pattern as the Ekiti portal load (`specs/0032-ekiti-html-portal-load.md`).

**Politeness**, because no rate-limit headers were observed (`Cache-Control: max-age=900` only):

- Wait at least 1 second between page requests.
- Send `User-Agent: NaijaLedger/govspend`.
- On HTTP 429 or 5xx, wait 5 seconds and retry that page once. If the retry also fails, stop the job. Stop immediately on 401 or 403.
- Follow the `next` URL from the body. Do not hard-code `last`.

The collection URL is a constant in code, not a caller-supplied URL.

## 4. Data contracts / schemas

### 4.1 Source seed

| Field | Value |
| --- | --- |
| name | BudgIT GovSpend — Federal payments |
| jurisdiction | `federal` |
| category | `payments` |
| url | `https://app.govspend.ng/api/payments/` |
| fetch_method | `api` |
| format | `json` |
| ingest_role | `leaf` |
| expected_cadence | `None` (loaded via CLI, not scheduled) |
| approved_by | `human:founder-2026-10-01` |

The `approved_by` field already exists on `sources` (added in migration 0001). Set it explicitly to `human:founder-2026-10-01` for this source. For OCDS sources with OCP-prefixed names, `approved_by` remains `None` (proposed status only) until a human reviews them.

`apply_seed_catalog` takes one run-wide `approved_by` argument (default `SEED_APPROVED_BY = "human:decision-brief-2026-07-07"`). Add an optional per-entry `approved_by` field to seed catalog entries. When the entry sets it, use that value in the `approve_source` call; otherwise keep the run-wide default. A fresh seed must leave the July sources at `human:decision-brief-2026-07-07`.

**Scheduling**: `expected_cadence=None` because `fetch_method=api` means the fetch-sources scheduler cannot run it (the scheduler walks `http`, `scrapling`, and `playwright` only). Run GovSpend loads via the dedicated CLI command (same pattern as Ekiti, spec 0032), or add a `govspend_load` job kind to the scheduler. Acceptance criterion: the source is never enqueued by `make fetch-sources`.

### 4.2 Page envelope (probed 2026-10-01)

```json
{
  "current": 1,
  "last": 4680,
  "next": "https://app.govspend.ng/api/payments/?page=2",
  "previous": null,
  "results": [ { "date": "2026-06-19", "payment_no": "1001450327-1", "payer_code": "0145001001", "organization_name": "PUBLIC COMPLAINTS COMMISSION", "beneficiary_name": "MANASIK TRAVEL AGENCY LTD", "amount": 22996722.0, "description": "…" } ]
}
```

`results` length on page 1 was 100. `amount` is a JSON number in naira, not kobo. `parse_govspend_page` must call `json.loads(data, parse_float=Decimal)`. Plain `json.loads` turns the token into a binary float before `Decimal` can see it. `1.005` naira is 101 kobo through `parse_float=Decimal` and 100 kobo through a float parse.

### 4.3 Row mapping

| GovSpend field | Canonical |
| --- | --- |
| `payment_no` | `payments.source_ref = "govspend:" + payment_no` (existing partial unique index) |
| `date` | `payments.paid_at` as UTC midnight (`YYYY-MM-DD`) |
| `amount` | `payments.amount` in kobo: `Decimal` naira × 100, round half up, `currency=NGN` |
| `description` | `payments.purpose` |
| `organization_name` | `parties` row, `party_type=agency` (payer). `payments.agency_id` |
| `payer_code` | `payments.meta.payer_code` on every loaded row. On insert of a new agency, also set `parties.identifiers.payer_code`. If the agency already exists, leave `parties.identifiers` unchanged. Do not call `_merge_identifiers` (`ocds_load.py`) with the incoming code: that helper overwrites the stored value. |
| `beneficiary_name` | `parties` row, `party_type=company`, when the name is non-blank. `payments.beneficiary_id`. Blank name → `beneficiary_id` null. |
| — | `payments.contract_id` stays null |
| — | `payments.meta.attribution = "BudgIT GovSpend (https://www.govspend.ng/)"` |
| — | `payments.meta.page_url` = the page URL that contained the row |

Skip the row (count it, do not fail the page) when `payment_no` is blank, `organization_name` is blank, `amount` is not a number, or `date` is not `YYYY-MM-DD`.

**Identity and upsert semantics**: Payments use their `source_ref` key (`govspend:{payment_no}`) as the primary identifier. They do **not** go through `load_normalized_release` or the OCDS identity system (issue #208 backfill and merge duplicates does not apply to payments). Upsert on `source_ref`: if a payment with that key exists, update `amount`, `paid_at`, `purpose`, party links, and `meta` in place.

**Provenance append-only**: `provenance_edges` rows are append-only per extraction. When re-loading a page, create a new extraction and new provenance edges for that extraction, even if the payment already exists. This preserves the audit trail of every fetch that observed the payment. To avoid redundant work, compute a `content_hash` (sha256 of canonical payment fields: `payment_no`, `date`, `amount`, `description`, `organization_name`, `beneficiary_name`, `payer_code`) and skip the upsert when the stored payment's `content_hash` matches the incoming row's hash. Still write the provenance edge to record that this extraction saw the same data.

Provenance: `method=json`, `derivation=extracted`, `confidence=1` (required by `ck_extractions_derivation_confidence` when derivation is `extracted`), `subject_type=payment`. `provenance_edges.region` is the JSON object `{"payment_no": "<payment_no>"}`, not a bare string. The document is the archived page.

**Note**: `ProvenanceContext.region` is already `dict[str, Any] | None` on main (widened in earlier work), so string payment numbers fit without schema changes.

### 4.4 Licence gate

Before the first load, a human must create `docs/licences/govspend.md` with:

- **Licence URL** (or "none published" if no public licence)
- **Terms summary** (or "none published")
- **Date reviewed** (YYYY-MM-DD)
- **Signed by** (human:founder or human:legal, not an agent)
- **Attribution requirement** (met by `meta.attribution` on every row)

The loader MUST check for this file at startup. If missing, fail immediately with error code `no_licence_record` and a message directing the operator to create the file. This is a fail-closed gate: no file = no load.

**PDDL or Open Database License detection**: Not implemented in this spec. The loader does not parse or verify licence terms automatically. It only checks that a human has documented the licence decision. The founder decides whether GovSpend's terms permit use. The Technical Counsel on the 2026-10-01 thread said BudgIT released the data publicly; formal licence confirmation is the founder's call.

### 4.5 Functions

```text
parse_govspend_page(data: bytes) -> list[GovSpendPayment]
naira_to_kobo(amount: Decimal) -> int
load_govspend_payments(connection, rows, *, provenance, page_url) -> LoadSummary
```

`GovSpendPayment` is a Pydantic model. Load summary reports inserted, updated, and skipped counts.

## 5. Acceptance criteria (testable)

- [ ] Fixture page with two valid rows loads two `payments`, two agency parties, beneficiary parties, and one provenance edge per payment. Amount `22996722.0` naira becomes `2299672200` kobo. `10.5` naira becomes `1050` kobo. `1.005` naira becomes `101` kobo via `json.loads(..., parse_float=Decimal)`.
- [ ] Each loaded row has `meta.attribution` = `BudgIT GovSpend (https://www.govspend.ng/)`, `meta.page_url` set to the page URL, and `meta.payer_code` set from the feed. The provenance edge has `confidence=1` and `region={"payment_no": "<payment_no>"}`.
- [ ] `source_ref` is `govspend:{payment_no}`. Reloading the same fixture creates a new extraction and new provenance edges, but does not add a second payment row (upsert on `source_ref`).
- [ ] When a payment's `content_hash` matches the stored value, the upsert is skipped (no write to `payments`), but a new provenance edge is still created to record that this extraction observed the same data.
- [ ] A row with a blank `payment_no` or a non-numeric `amount` is skipped and counted.
- [ ] Blank `beneficiary_name` leaves `beneficiary_id` null.
- [ ] An existing agency whose stored `payer_code` differs from the row keeps `parties.identifiers` unchanged. The payment row still records the feed's `payer_code` in `meta`.
- [ ] A fresh seed leaves July sources at `approved_by=human:decision-brief-2026-07-07` and sets the GovSpend row to `human:founder-2026-10-01`.
- [ ] CLI default `max_pages` is 2. Unit tests do not call the network.
- [ ] Loader does not request any `/download` path.
- [ ] The GovSpend source is never enqueued by `make fetch-sources` (test: seed the source, run the scheduler, assert the source is not in the queue).
- [ ] If `docs/licences/govspend.md` is missing, the loader fails immediately with error code `no_licence_record` before attempting any network requests.

## 6. Risks & mitigations

- **Secondary source.** GovSpend is mined from Open Treasury, not the official file. Mitigation: attribution on every row; keep Open Treasury retired until its TLS is fixed; official file stays a separate legal ask.
- **Name mismatch.** Payer strings may not equal Budget Office agency names, so `budget_payment_mismatch` can miss or false-hit. Mitigation: no fuzzy match in this spec. Matching is a follow-up.
- **Float money.** JSON numbers are binary floats. Mitigation: `json.loads(..., parse_float=Decimal)`, then half-up to kobo.
- **All beneficiaries stored as companies.** A person paid directly will be typed `company`. Mitigation: accepted for v1; split later if the feed grows a type field.
- **No published terms of use.** Founder approved use on 2026-10-01 without an email. Mitigation: rate limit, credit, sample cap. Stop the job if the API starts returning 401 or 403. Licence gate (§4.4) ensures a human documents the licence decision before the first load.
- **Layout drift.** Missing `results` fails the page with a clear error rather than writing zero rows silently.
- **History loss on in-place upserts.** Payments are updated in place when `source_ref` matches. If GovSpend silently corrects an amount or date after publication, the stored row reflects the new value and the old value is lost (provenance edges remain append-only, but the payment row itself is overwritten). Mitigation: accepted for v1. A full audit trail would require a separate `payments_history` table or a migration to immutable event sourcing. For now, the `content_hash` skip (§4.3) reduces redundant writes, and provenance edges show when the row was observed, but diffing historical values is not supported.

## 7. Open questions

None blocking. Full backfill (about 4,680 pages) uses the same loader with a higher `max_pages` after the sample looks right. Do not run that backfill as part of the first implementation PR.

## 8. Founder decisions needed

Two architectural decisions require explicit founder approval before implementation:

1. **Licence gate (§4.4)**: The loader requires `docs/licences/govspend.md` to exist before it runs (fail-closed with `no_licence_record` error if missing). The founder must confirm this is the right approach, and must create that file to document BudgIT GovSpend's licence terms (or "none published"), attribution requirements, and sign off that use is permitted. The Technical Counsel on the 2026-10-01 thread said BudgIT released the data publicly; formal confirmation is the founder's call.

2. **In-place upsert with history loss (§4.3, §6 risk 7)**: Payments are updated in place when their `source_ref` key matches. If GovSpend silently corrects an amount after publication, the old value is lost (only the new value remains in the `payments` table). Provenance edges are append-only, so we know *when* the row was observed, but we cannot diff *what changed*. A full audit trail would require a `payments_history` table or event-sourcing migration. The founder must accept this history-loss trade-off for v1, or request the implementation add a history table before the first load.

Label this PR `needs-human` until these decisions are confirmed.
