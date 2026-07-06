# Narevo — Data Model

> Status: **Draft v0.1** · Derives from `SYSTEM_DESIGN.md`. Postgres is canonical (P6);
> Neo4j/search/vector are rebuildable projections.

## Conventions
- All tables have `id` (uuid), `created_at`, `updated_at`.
- Timestamps are UTC. Money stored as integer minor units + `currency` (default `NGN`).
- Nothing is hard-deleted in evidentiary tables; use `retracted_at` + reason.

---

## Ingestion & provenance

### `sources`
Catalog of every place we get data from.
| column | type | notes |
|---|---|---|
| name | text | human label |
| jurisdiction | enum | `federal|state|lga` |
| region | text | e.g. `Lagos` (nullable) |
| category | enum | `budget|procurement|payments|company|election|other` |
| url | text | base/entry URL |
| fetch_method | enum | `http|scrapling|playwright|api|manual` |
| format | enum | `pdf|xlsx|csv|json|html|image` |
| expected_cadence | interval | for scheduling |
| last_fetched_at | timestamptz | nullable |
| last_success_hash | text | sha256 of last good payload |
| schema_fingerprint | text | detect drift |
| health_status | enum | `healthy|degraded|down|tls_expired|unknown` |
| reliability_score | numeric | 0–1 |
| status | enum | `proposed|approved|retired` (discovery agent → human approves) |
| added_by / approved_by | text | agent or user id |

### `fetch_records`
One row per fetch attempt (evidentiary).
`source_id, url, requested_at, status_code, ok bool, byte_count, sha256, headers jsonb, error, archive_key`

### `documents`
A distinct artifact (a specific PDF/XLSX/JSON/image) identified by content hash.
`source_id, first_fetch_id, sha256 (unique), format, archive_key, title, published_at, meta jsonb`

### `extractions`
Result of parsing a document (versioned by extractor).
`document_id, extractor (enum: peadf_pdfjs|peadf_ocr|tables|xlsx|json|vision_llm), extractor_version,
ok bool, payload jsonb, ocr_used bool, created_at`

### `provenance_edges`
Ties any canonical record back to evidence.
`subject_type, subject_id, document_id, extraction_id, page int, region jsonb (bbox),
method, verified_by, verified_at`

---

## Public-finance domain (OCDS-aligned)

### `parties` (polymorphic via `party_type`)
`party_type enum: company|person|agency`, `canonical_name`, `aliases text[]`,
`identifiers jsonb` (RC number/CAC id, TIN, etc.), `address jsonb`, `merged_into_id` (entity res.)

### `party_relationships`
`from_party_id, to_party_id, relationship enum: owns|director_of|significant_control|same_address|associated,
weight, source provenance`

### `tenders`
`ocid text, agency_id (party), title, method enum: open|selective|limited|direct, value_amount,
currency, bidding_opens_at, bidding_closes_at, meta jsonb`

### `awards`
`tender_id, supplier_id (party), value_amount, currency, awarded_at, meta jsonb`

### `contracts`
`award_id, supplier_id, agency_id, value_amount, currency, signed_at, period jsonb, status, meta jsonb`

### `payments`
`contract_id (nullable), agency_id, beneficiary_id (party, nullable), amount, currency, paid_at,
purpose, source_ref (e.g. Open Treasury row), meta jsonb`

### `budget_lines`
`fiscal_year, agency_id, code, description, allocated_amount, revised_amount, released_amount,
utilised_amount, jurisdiction, region`

---

## Election domain

### `polling_units`
`inec_code (unique), name, ward, lga, state, geo point, registered_voters int`

### `polling_unit_results`
`polling_unit_id, election_id, party_code, votes int, accredited_voters int, registered_voters int,
source enum: ec8a_photo|irev|collation, document_id, captured_at, observer_ref (hashed), meta jsonb`

### `result_crosschecks`
`polling_unit_id, election_id, ec8a_value, irev_value, collation_value, overvote bool,
discrepancy jsonb, status enum: match|mismatch|missing_irev|under_review`

---

## Analysis & review

### `flags`
`subject_type, subject_id, rule enum (single_bidder|short_window|threshold_hugging|repeat_winner|
shared_address|price_outlier|budget_payment_mismatch|overvote|...), severity, evidence jsonb,
status enum: open|dismissed|confirmed, created_by (agent), reviewed_by`

### `review_decisions`
`subject_type, subject_id, decision enum: approve_publish|reject|needs_more_evidence,
reviewer, rationale, decided_at` — enforces P3 (human-in-the-loop before publication).

### `transparency_log`
`leaf_hash, tree_size, root_hash, anchored_at, anchor_ref` — Merkle log for tamper-evidence (§5.2).

---

## Graph projection (Neo4j — rebuildable)
Nodes: `Company`, `Person`, `Agency`, `Contract`, `Tender`, `Award`.
Edges: `OWNED_BY`, `DIRECTOR_OF`, `SIGNIFICANT_CONTROL`, `SAME_ADDRESS`, `WON`, `AWARDED_BY`,
`PAID`. Rebuilt from `parties`, `party_relationships`, `awards`, `contracts`, `payments`.
