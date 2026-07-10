# NaijaLedger — Data Model

> Status: **Draft v0.1** · Derives from `SYSTEM_DESIGN.md`. Postgres is canonical (P6);
> Memgraph/search/vector are rebuildable projections.

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
Result of parsing a document (versioned by method). See `specs/0009-extraction-contract.md`.
`document_id, method (xlsx|csv|json|pdf_text|pdf_table|ocr|vision_llm), method_version,
derivation (extracted|inferred|ambiguous), confidence numeric(4,3), ok bool, payload jsonb,
content_type, content_type_conf, status (parsed|quarantined|unsupported|failed), created_at`
- `derivation=extracted` ⇒ `confidence=1.0`; `inferred`/`ambiguous` ⇒ `confidence < 1.0`.

### `provenance_edges`
Ties any canonical record (or pre-canonical extraction block) back to evidence.
`subject_type, subject_id` (nullable until E5 links a canonical subject),
`document_id, extraction_id, page int, region jsonb (bbox), method, derivation, confidence,
verified_by, verified_at`

---

## Public-finance domain (OCDS-aligned)

Money: integer **minor units** (kobo) + `currency` (default `NGN`). See `specs/0011-canonical-finance-schema.md`.

### `parties` (polymorphic via `party_type`)
`party_type` (`company|person|agency`), `canonical_name`, `aliases text[]`,
`identifiers jsonb` (RC/CAC/TIN/etc.), `address jsonb`, `merged_into_id` (entity res.),
unique `(party_type, lower(canonical_name))` for v1 upsert.

### `party_relationships`
`from_party_id, to_party_id, relationship` (`owns|director_of|significant_control|same_address|associated`),
`weight`, unique `(from, to, relationship)`.

### `tenders`
`ocid` (unique when present), `agency_id` → parties, `title`, `method`
(`open|selective|limited|direct`), `value_amount` (kobo), `currency`, bidding window, `meta`.

### `awards`
`tender_id`, `supplier_id` → parties, `value_amount`, `currency`, `awarded_at`, `meta`.

### `contracts`
`award_id` (nullable), `supplier_id`, `agency_id`, `value_amount`, `currency`, `signed_at`,
`period jsonb`, `status`, `meta`.

### `payments`
`contract_id` (nullable), `agency_id`, `beneficiary_id` (nullable), `amount`, `currency`,
`paid_at`, `purpose`, `source_ref` (unique when present), `meta`.

### `budget_lines`
`fiscal_year`, `agency_id`, `code`, `description`, allocated/revised/released/utilised amounts,
`currency`, `jurisdiction`, `region`; unique `(fiscal_year, agency_id, code, jurisdiction)`.


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
Anomaly hypotheses (never auto-published claims). See `specs/0017-anomaly-flags.md`.
`subject_type, subject_id, rule` (`single_bidder|short_window|threshold_hugging|repeat_winner|
shared_address|price_outlier|budget_payment_mismatch|overvote|smoke`), `severity`
(`low|medium|high`), `evidence jsonb` (requires `summary`), `status`
(`open|dismissed|confirmed`), `created_by`, `reviewed_by`, `reviewed_at`; unique open
`(rule, subject_type, subject_id)`; sticky non-open rows suppress re-open on re-run.

### `review_decisions`
`subject_type, subject_id, decision enum: approve_publish|reject|needs_more_evidence,
reviewer, rationale, decided_at` — enforces P3 (human-in-the-loop before publication).

### `party_match_proposals` (E6.2)
Pending entity-resolution judgments. See `specs/0015-llm-match-adjudication.md`.
`left_party_id, right_party_id, match_score, match_rule, match_reason, opinion
(same_entity|different|uncertain), opinion_rationale, adjudicator, status
(pending|confirmed|rejected|withdrawn), suggested_survivor_id, resolved_by, resolved_at, meta`.
Human confirm is required before `apply_party_merge`; LLM opinion is advisory only.

### `transparency_log`
`leaf_hash, tree_size, root_hash, anchored_at, anchor_ref` — Merkle log for tamper-evidence (§5.2).

---

## Graph projection (Memgraph — rebuildable)

See `specs/0016-graph-projection.md`. Labels: Agency/Company/Person/FinanceParty/Tender/Award/Contract;
edges ISSUED, RESULTED_IN, AWARDED_TO, CONTRACTED, SUPPLIED, FROM_AWARD. Ownership edges
(`OWNED_BY`, etc.) land after E6.3. Rebuilt from Postgres; never the source of truth.
