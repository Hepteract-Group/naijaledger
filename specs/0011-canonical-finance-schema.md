# Spec 0011 — Canonical public-finance schema (E5.1)

- **Epic / Issue**: E5.1 / #32
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — columns derive from `docs/architecture/data-model.md`; money as
  integer minor units + `currency` (default `NGN`) per conventions.

## 1. Problem

E4 produces `extractions` blocks. E5 must land **normalized** public-finance facts in Postgres
(the canonical store) before graph projection, anomalies, or publication. Without the core tables
(`parties`, `tenders`, `awards`, `contracts`, `payments`, `budget_lines` + relationships), the
OCDS normalizer (#33) and provenance wiring (#34) have nowhere to write.

Derives from `SYSTEM_DESIGN.md` §4.5–4.7 and `data-model.md` §Public-finance domain.

## 2. Scope & non-scope

- **In scope**
  - Alembic migration creating the finance tables listed below (with FKs, CHECKs, useful indexes).
  - Align `data-model.md` if any column is tightened for implementability.
  - Minimal Pydantic models + `get_*` / `create_*` service stubs sufficient for tests and #33.
- **Out of scope**
  - OCDS field mapping / parsers (#33).
  - Writing `provenance_edges.subject_*` from normalizer (#34) — schema already exists; wiring later.
  - Full idempotent upsert policy (#35) — this spec only adds **natural-key unique constraints**
    the upsert layer will use.
  - Election tables (E11).
  - Entity-resolution merge UI / LLM adjudication (E6) — only `merged_into_id` column on `parties`.

## 3. Design

### 3.1 Conventions

- Every table: `id uuid pk`, `created_at`, `updated_at` (timestamptz, default `now()`).
- Money: `bigint` **kobo** (minor units) + `currency text not null default 'NGN'`.
- No hard deletes on evidentiary rows; soft patterns deferred (no `retracted_at` in v1 unless needed).
- Enums as `text` + `CHECK` (same pattern as `jobs` / `extractions`) for migration flexibility.

### 3.2 Entity sketch

```
parties ←── party_relationships ──→ parties
   ↑
   ├── tenders.agency_id
   ├── awards.supplier_id (+ tender_id → tenders)
   ├── contracts.supplier_id / agency_id (+ award_id → awards)
   ├── payments.agency_id / beneficiary_id (+ optional contract_id)
   └── budget_lines.agency_id
```

## 4. Data contracts / schemas

### 4.1 `parties`

```
parties(
  id uuid pk,
  party_type text not null CHECK (party_type IN ('company','person','agency')),
  canonical_name text not null,
  aliases text[] not null default '{}',
  identifiers jsonb not null default '{}',  -- e.g. {"rc":"...", "tin":"..."}
  address jsonb null,
  merged_into_id uuid null REFERENCES parties(id) ON DELETE RESTRICT,
  meta jsonb null,
  created_at, updated_at
)
CREATE INDEX ix_parties_canonical_name ON parties (canonical_name);
CREATE INDEX ix_parties_merged_into ON parties (merged_into_id) WHERE merged_into_id IS NOT NULL;
-- Natural key for upsert (#35): type + lower(name); refine with identifiers later in E6.
CREATE UNIQUE INDEX uq_parties_type_name ON parties (party_type, lower(canonical_name));
```

### 4.2 `party_relationships`

```
party_relationships(
  id uuid pk,
  from_party_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  to_party_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  relationship text not null CHECK (relationship IN (
    'owns','director_of','significant_control','same_address','associated'
  )),
  weight numeric(4,3) null CHECK (weight IS NULL OR (weight >= 0 AND weight <= 1)),
  meta jsonb null,           -- may hold provenance refs until #34 fills edges
  created_at, updated_at,
  CHECK (from_party_id <> to_party_id),
  UNIQUE (from_party_id, to_party_id, relationship)
)
```

### 4.3 `tenders`

```
tenders(
  id uuid pk,
  ocid text null,
  agency_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  title text not null,
  method text null CHECK (method IS NULL OR method IN (
    'open','selective','limited','direct'
  )),
  value_amount bigint null,          -- kobo
  currency text not null default 'NGN',
  bidding_opens_at timestamptz null,
  bidding_closes_at timestamptz null,
  meta jsonb null,
  created_at, updated_at
)
CREATE UNIQUE INDEX uq_tenders_ocid ON tenders (ocid) WHERE ocid IS NOT NULL;
CREATE INDEX ix_tenders_agency_id ON tenders (agency_id);
```

### 4.4 `awards`

```
awards(
  id uuid pk,
  tender_id uuid not null REFERENCES tenders(id) ON DELETE RESTRICT,
  supplier_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  value_amount bigint null,
  currency text not null default 'NGN',
  awarded_at timestamptz null,
  meta jsonb null,
  created_at, updated_at
)
CREATE INDEX ix_awards_tender_id ON awards (tender_id);
CREATE INDEX ix_awards_supplier_id ON awards (supplier_id);
```

### 4.5 `contracts`

```
contracts(
  id uuid pk,
  award_id uuid null REFERENCES awards(id) ON DELETE RESTRICT,
  supplier_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  agency_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  value_amount bigint null,
  currency text not null default 'NGN',
  signed_at timestamptz null,
  period jsonb null,                 -- {"start":"...","end":"..."}
  status text null,
  meta jsonb null,
  created_at, updated_at
)
CREATE INDEX ix_contracts_award_id ON contracts (award_id);
CREATE INDEX ix_contracts_supplier_id ON contracts (supplier_id);
CREATE INDEX ix_contracts_agency_id ON contracts (agency_id);
```

### 4.6 `payments`

```
payments(
  id uuid pk,
  contract_id uuid null REFERENCES contracts(id) ON DELETE RESTRICT,
  agency_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  beneficiary_id uuid null REFERENCES parties(id) ON DELETE RESTRICT,
  amount bigint not null,
  currency text not null default 'NGN',
  paid_at timestamptz null,
  purpose text null,
  source_ref text null,              -- e.g. Open Treasury row id
  meta jsonb null,
  created_at, updated_at
)
CREATE UNIQUE INDEX uq_payments_source_ref ON payments (source_ref)
  WHERE source_ref IS NOT NULL;
CREATE INDEX ix_payments_agency_id ON payments (agency_id);
CREATE INDEX ix_payments_contract_id ON payments (contract_id);
```

### 4.7 `budget_lines`

```
budget_lines(
  id uuid pk,
  fiscal_year int not null,
  agency_id uuid not null REFERENCES parties(id) ON DELETE RESTRICT,
  code text not null,
  description text null,
  allocated_amount bigint null,
  revised_amount bigint null,
  released_amount bigint null,
  utilised_amount bigint null,
  currency text not null default 'NGN',
  jurisdiction text not null CHECK (jurisdiction IN ('federal','state','lga')),
  region text null,
  meta jsonb null,
  created_at, updated_at,
  UNIQUE (fiscal_year, agency_id, code, jurisdiction)
)
```

## 5. Acceptance criteria (testable)

- [ ] Migration creates all seven tables with FKs and CHECKs above.
- [ ] Inserting a `tender` with unknown `agency_id` fails FK.
- [ ] Duplicate `(party_type, lower(canonical_name))` fails unique index.
- [ ] Duplicate `payments.source_ref` (non-null) fails unique index.
- [ ] Duplicate `tenders.ocid` (non-null) fails unique index.
- [ ] Service can `create_party` / `get_party` round-trip (functional, Connection-passed).

## 6. Risks & mitigations

- **Name-only unique on parties is brittle** — acceptable v1; E6 will prefer identifier-based
  matching and `merged_into_id`. Document that normalizer should populate `identifiers` early.
- **OCDS method vocabulary drift** — CHECK list matches data-model; widen via migration if needed.
- **Large meta jsonb** — keep structured columns first-class; meta is overflow only.

## 7. Open questions

None blocking. Follow-ups: #33 OCDS mapping, #34 provenance subject wiring, #35 upsert helpers.
