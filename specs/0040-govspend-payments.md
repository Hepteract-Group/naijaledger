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
GET https://app.govspend.ng/api/payments/?page=N (timeout 30s, byte cap 10MB)
  → archive page bytes + fetch_record (before parse)
  → with engine.begin() as connection:  # one transaction per page
      → parse_govspend_page
      → on parse failure: write failed extraction, STOP (no next URL)
      → create_extraction(method=json)
      → for each row:
          → with connection.begin_nested():  # savepoint per row
              → upsert parties + payments (skip if content_hash unchanged)
              → provenance_edge (append-only)
          → on row load error: rollback savepoint, continue next row
      → COMMIT transaction
  → follow `next` until null, empty page, or max_pages
```

**Transaction isolation**: One `engine.begin()` transaction per page with a savepoint per row (`begin_nested()`). On a **parse failure** (invalid JSON, missing `results`, etc.), write a failed extraction and **STOP** the job—there is no `next` URL from a failed parse. On a **load error** for a row that parsed successfully (e.g. party insert conflict, invalid date), roll back that row's savepoint and continue to the next row. Commit page by page so partial runs are resumable.

**Response caps and timeout**: 30-second timeout per page request (same as OCP `PAGE_TIMEOUT_S`). 10 MB byte cap per page response (uncompressed). If the response exceeds the cap or the request times out, archive the partial or error response, write a failed fetch record, and stop the job.

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

The `approved_by` field already exists on `sources` (added in migration 0001). Set it explicitly to `human:founder-2026-10-01` for this source.

`SourceCreate.approved_by` is **not** a DB column—it is a seed-time field used by `apply_seed_catalog`. When a catalog entry sets `approved_by`, that value is used in `approve_source`; otherwise the run-wide default applies (`SEED_APPROVED_BY = "human:decision-brief-2026-07-07"`). A fresh seed must leave the July sources at `human:decision-brief-2026-07-07`.

**Note**: The architect's claim that OCP-prefixed sources stay `approved_by=None` is **false**. Seven OCP state sources are `human:issue-203` (approved in PR #207). Only Oyo and Plateau remain `None` (proposed status). `apply_seed_catalog` has a None trap (line 248): when `entry.approved_by is None` and the name starts with `"OCP Data Registry"`, the source is marked `explicitly_proposed` and demoted to proposed status even if it was already approved.

**Scheduling**: `expected_cadence=None` because `fetch_method=api` means the fetch-sources scheduler cannot run it (the scheduler walks `http`, `scrapling`, and `playwright` only). Run GovSpend loads via the dedicated CLI command (same pattern as Ekiti, spec 0032). Acceptance criterion: the source is never enqueued by `enqueue_due_fetch_jobs` (`jobs/service.py:137`).

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

**Provenance append-only**: `provenance_edges` rows are append-only per extraction. When re-loading a page, create a new extraction and new provenance edges for that extraction, even if the payment already exists. This preserves the audit trail of every fetch that observed the payment. To avoid redundant work, compute a `content_hash` and store it in `payments.meta.content_hash`. Skip the upsert when the stored hash matches the incoming row's hash. Still write the provenance edge to record that this extraction saw the same data.

**content_hash canonicalisation**: sha256 hex digest of a UTF-8 JSON object with fields in this exact order: `payment_no`, `date`, `amount`, `description`, `organization_name`, `beneficiary_name`, `payer_code`. Serialize `Decimal` amounts as strings (e.g. `"22996722.0"`). Nulls serialize as JSON `null`. Example: `{"payment_no": "1001450327-1", "date": "2026-06-19", "amount": "22996722.0", "description": "...", "organization_name": "PUBLIC COMPLAINTS COMMISSION", "beneficiary_name": "MANASIK TRAVEL AGENCY LTD", "payer_code": "0145001001"}`. The `payments` table has no `content_hash` column; store it in `meta.content_hash`.

Provenance: `method=json`, `derivation=extracted`, `confidence=1` (required by `ck_extractions_derivation_confidence` when derivation is `extracted`), `subject_type=payment`. `provenance_edges.region` is the JSON object `{"payment_no": "<payment_no>"}`, not a bare string. The document is the archived page.

**Note**: `ProvenanceContext.region` is already `dict[str, Any] | None` on main (widened in earlier work), so string payment numbers fit without schema changes.

### 4.4 Licence gate

Before the first load, a human must create `docs/licences/govspend.md` in the **same format** parsed by `parse_licence_record` (`finance/ocp_registry.py`):

```markdown
**Publication URL**: <url or "none published">
**Licence phrase as read**: <phrase or "none published">
**Date read**: YYYY-MM-DD
**Signed by**: human:founder
```

The loader MUST call `parse_licence_record` (or name a separate parser if the format differs). If the file is missing or unparseable, fail immediately with error code `no_licence_record` and a message directing the operator to create the file. This is a fail-closed gate: no file = no load.

**Signed by format**: Must be exactly `human:founder` or `human:legal`, matching the format used in OCP licence records. Not an agent signature.

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
- [ ] The GovSpend source is never enqueued by `enqueue_due_fetch_jobs` (test: seed the source, call `enqueue_due_fetch_jobs`, assert the source is not in the returned `inserted` count or the jobs queue).
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

None beyond §8. Full backfill (about 4,680 pages) uses the same loader with a higher `max_pages` after the sample looks right. Do not run that backfill as part of the first implementation PR.

## 8. Founder decisions needed

Six decisions require explicit founder approval before implementation. Each has a stated default if there is no answer:

1. **Licence gate (§4.4)**: The loader requires `docs/licences/govspend.md` to exist before it runs (fail-closed with `no_licence_record` error if missing). The founder must create that file to document BudgIT GovSpend's licence terms (or "none published") and sign off that use is permitted. The Technical Counsel on the 2026-10-01 thread said BudgIT released the data publicly; formal licence confirmation is the founder's call.
   - **Default if no answer**: Proceed with the fail-closed gate. Implementation blocks until the file exists.

2. **In-place upsert with history loss (§4.3, §6 risk 7)**: Payments are updated in place when their `source_ref` key matches. If GovSpend silently corrects an amount after publication, the old value is lost (only the new value remains in the `payments` table). Provenance edges are append-only, so we know *when* the row was observed, but we cannot diff *what changed*. A full audit trail would require a `payments_history` table or event-sourcing migration.
   - **Default if no answer**: Accept history loss for v1. No history table in the first implementation.

3. **Full backfill go/no-go**: After the 2-page sample loads successfully, run the full ~4,680-page backfill to load all federal payments. This will take hours and write ~468,000 rows. The founder must sign off on the backfill, or defer it until the sample data has been reviewed.
   - **Default if no answer**: Do not run the backfill automatically. Wait for explicit sign-off.

4. **Backfill sign-off authority**: Who authorizes the full backfill? The founder, or can a technical lead approve it after reviewing the sample?
   - **Default if no answer**: Founder only.

5. **Email to BudgIT**: The 2026-10-01 decision said not to send the partnership email unless the founder asks for an email trail. Confirm this remains the decision, or send the email before the first load.
   - **Default if no answer**: Continue not emailing BudgIT. Email only if the founder explicitly asks.

6. **Accept v1 shortcuts**:
   - All beneficiaries are typed `party_type=company`, even if a person was paid directly. No person/company split.
   - No fuzzy match of payer names onto Budget Office agency names. `budget_payment_mismatch` may false-hit or miss.
   - **Default if no answer**: Accept both shortcuts for v1. Matching and party-type refinement are follow-up work.

Label this PR `needs-human` until these decisions are confirmed.
