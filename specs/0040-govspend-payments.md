# Spec 0040 — BudgIT GovSpend payments ingest

- **Epic / Issue**: E5 / #179 (decision recorded on #172, 2026-10-01)
- **Status**: Approved
- **Author**: agent
- **Needs human decision?**: no — founder approved GovSpend on 2026-10-01 and said to proceed without sending the partnership email. Send that email only if the founder later asks for an email trail.

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
  → create_extraction(method=json)
  → upsert parties + payments
  → provenance_edge subject_type=payment, region={"payment_no": "<payment_no>"}
  → follow `next` until null, empty page, or max_pages
```

`make fetch-sources` walks `http`, `scrapling`, and `playwright` only. This source uses `fetch_method=api` so that walker skips it. Loading is a dedicated command, same pattern as the Ekiti portal load (`specs/0032-ekiti-html-portal-load.md`).

Politeness, because no rate-limit headers were observed (`Cache-Control: max-age=900` only):

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
| expected_cadence | 7 days |
| approved_by | `human:founder-2026-10-01` |

`apply_seed_catalog` takes one run-wide `approved_by`, default `SEED_APPROVED_BY` (`human:decision-brief-2026-07-07`). Do not pass `human:founder-2026-10-01` as that argument. Add an optional `approved_by` on the seed catalog entry. When the entry sets it, use that value for `approve_source`; otherwise keep the run-wide default. `ingest_role=leaf` is already in the auto-approve set. A fresh seed must leave the July sources on `human:decision-brief-2026-07-07`.

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

Upsert on `source_ref`. A second load of the same page updates amount, paid_at, purpose, party links, and meta, and does not insert a second `provenance_edges` row for the same extraction + payment.

Provenance: `method=json`, `derivation=extracted`, `confidence=1` (required by `ck_extractions_derivation_confidence` when derivation is `extracted`), `subject_type=payment`. `provenance_edges.region` is the JSON object `{"payment_no": "<payment_no>"}`, not a bare string. Widen `ProvenanceContext.region` from `dict[str, float] | None` to `dict[str, str | float] | None` so the payment number fits. Coordinate dicts used by other loaders stay valid. The document is the archived page.

### 4.4 Functions

```text
parse_govspend_page(data: bytes) -> list[GovSpendPayment]
naira_to_kobo(amount: Decimal) -> int
load_govspend_payments(connection, rows, *, provenance, page_url) -> LoadSummary
```

`GovSpendPayment` is a Pydantic model. Load summary reports inserted, updated, and skipped counts.

## 5. Acceptance criteria (testable)

- [ ] Fixture page with two valid rows loads two `payments`, two agency parties, beneficiary parties, and one provenance edge per payment. Amount `22996722.0` naira becomes `2299672200` kobo. `10.5` naira becomes `1050` kobo. `1.005` naira becomes `101` kobo via `json.loads(..., parse_float=Decimal)`.
- [ ] Each loaded row has `meta.attribution` = `BudgIT GovSpend (https://www.govspend.ng/)`, `meta.page_url` set to the page URL, and `meta.payer_code` set from the feed. The provenance edge has `confidence=1` and `region={"payment_no": "<payment_no>"}`.
- [ ] `source_ref` is `govspend:{payment_no}`. Reloading the same fixture does not add a second payment or a second provenance edge.
- [ ] A row with a blank `payment_no` or a non-numeric `amount` is skipped and counted.
- [ ] Blank `beneficiary_name` leaves `beneficiary_id` null.
- [ ] An existing agency whose stored `payer_code` differs from the row keeps `parties.identifiers` unchanged. The payment row still records the feed's `payer_code` in `meta`.
- [ ] A fresh seed leaves July sources at `approved_by=human:decision-brief-2026-07-07` and sets the GovSpend row to `human:founder-2026-10-01`.
- [ ] CLI default `max_pages` is 2. Unit tests do not call the network.
- [ ] Loader does not request any `/download` path.

## 6. Risks & mitigations

- **Secondary source.** GovSpend is mined from Open Treasury, not the official file. Mitigation: attribution on every row; keep Open Treasury retired until its TLS is fixed; official file stays a separate legal ask.
- **Name mismatch.** Payer strings may not equal Budget Office agency names, so `budget_payment_mismatch` can miss or false-hit. Mitigation: no fuzzy match in this spec. Matching is a follow-up.
- **Float money.** JSON numbers are binary floats. Mitigation: `json.loads(..., parse_float=Decimal)`, then half-up to kobo.
- **All beneficiaries stored as companies.** A person paid directly will be typed `company`. Mitigation: accepted for v1; split later if the feed grows a type field.
- **No published terms of use.** Founder approved use on 2026-10-01 without an email. Mitigation: rate limit, credit, sample cap. Stop the job if the API starts returning 401 or 403.
- **Layout drift.** Missing `results` fails the page with a clear error rather than writing zero rows silently.

## 7. Open questions

None blocking. Full backfill (about 4,680 pages) uses the same loader with a higher `max_pages` after the sample looks right. Do not run that backfill as part of the first implementation PR.
