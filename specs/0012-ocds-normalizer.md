# Spec 0012 — OCDS normalizer mapping (E5.2)

- **Epic / Issue**: E5.2 / #33
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — map OCDS release fields onto E5.1 tables; money as kobo;
  thin natural-key upserts (full re-run policy remains #35).

## 1. Problem

E4 can parse JSON documents into extraction blocks. Federal/state OCDS portals (NOCOPO, Ekiti,
Adamawa, …) emit **OCDS releases** (or release packages). Without a normalizer, those payloads
never become `parties` / `tenders` / `awards` / `contracts` rows in the canonical store.

Derives from `SYSTEM_DESIGN.md` §4.5–4.7, `data-model.md` §Public-finance domain, and
`specs/0011-canonical-finance-schema.md`.

## 2. Scope & non-scope

- **In scope**
  - Pure mapping: OCDS **release** (and **release package** wrapper) → typed finance DTOs.
  - Field map for parties, tender, awards, contracts (payments/budget_lines are non-OCDS → out).
  - Money → kobo + currency; `procurementMethod` → our CHECK vocabulary.
  - Thin loader: write DTOs via `Connection` using natural-key upserts already in E5.1
    (`parties` type+lower(name), `tenders.ocid`).
  - Unit tests on fixture releases (no live portal fetch).
- **Out of scope**
  - HTML/table scrapes that are not OCDS JSON (Kaduna cards, Benue, etc.) — separate adapters later.
  - Writing `provenance_edges.subject_*` (#34).
  - Full idempotent upsert / merge policy across re-runs and conflicting sources (#35).
  - Entity-resolution beyond get-or-create by `(party_type, lower(canonical_name))` (E6).
  - `party_relationships` from beneficial ownership (E6 / CAC).
  - Scheduling extract→normalize jobs (follow-up on jobs kinds).

## 3. Design

### 3.1 Input shapes

Accept a Python `dict` that is either:

1. **Release** — has `ocid` and usually `tender` / `awards` / `contracts` / `parties`.
2. **Release package** — has `releases: list[release]`; normalize each release and concatenate.

Reject (raise typed error or return empty with reason) payloads that are neither.

Extraction blocks from `parse_json` wrap values as `{"value": <obj>}` (and optionally `index`).
A small adapter unwraps that before calling the release normalizer:

```text
extraction block.payload → unwrap → release|package → NormalizedBundle
```

### 3.2 Flow

```text
OCDS JSON
   │
   ▼
unwrap_extraction_payload (optional)
   │
   ▼
normalize_ocds_document(doc) ──► list[NormalizedRelease]
   │
   ▼
load_normalized_release(conn, release)   # thin upsert; no provenance yet
```

Pure functions first; I/O only in `load_*`.

### 3.3 Party typing

| OCDS role / hint | `party_type` |
|---|---|
| `buyer`, `procuringEntity`, party with role containing those | `agency` |
| `supplier`, `tenderer` | `company` (default; person only if clearly individual — v1 always `company`) |
| unknown | `company` if supplier-like else `agency` for buyer-like; else `company` |

`canonical_name` from `name` (required to emit a party). Identifiers: copy `id` / `identifier` /
`additionalIdentifiers` into `identifiers` jsonb (`ocds_id`, `scheme`, `id`, …).

### 3.4 Tender / award / contract

- **Tender**: `ocid` from release; `title` from `tender.title`; `method` from
  `tender.procurementMethod` mapped below; `value_amount` from `tender.value`; agency from buyer /
  procuringEntity party (required — skip tender write if no agency resolvable).
- **Awards**: each `awards[]` item → one row per supplier (OCDS may list multiple suppliers);
  link `tender_id` after tender upsert; `awarded_at` from `date`.
- **Contracts**: each `contracts[]` item; link `award_id` when `awardID` matches an award in the
  same release; supplier/agency from contract parties or fall back to award/tender parties;
  `signed_at` from `dateSigned` / `date`; `period` jsonb from `period`; `status` text as-is.

Items missing required FK targets are skipped and recorded in a `skipped` list on the result
(not silent data loss).

### 3.5 Method vocabulary

| OCDS `procurementMethod` | Ours |
|---|---|
| `open` | `open` |
| `selective` | `selective` |
| `limited` | `limited` |
| `direct` | `direct` |
| other / missing | `null` (store raw in `tenders.meta.procurementMethod`) |

### 3.6 Money

```text
amount_major * 100 → bigint kobo (ROUND_HALF_UP)
currency from Amount.currency or default NGN
```

Non-numeric / missing amount → `null` amount fields (except `payments.amount` which is N/A here).

## 4. Data contracts / schemas

### 4.1 DTOs (Pydantic)

```python
class NormalizedParty(BaseModel):
    party_type: PartyType
    canonical_name: str
    aliases: list[str] = []
    identifiers: dict[str, Any] = {}
    address: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None

class NormalizedTender(BaseModel):
    ocid: str
    agency_ref: str          # stable key into parties map for this release
    title: str
    method: TenderMethod | None
    value_amount: int | None  # kobo
    currency: str = "NGN"
    bidding_opens_at: datetime | None
    bidding_closes_at: datetime | None
    meta: dict[str, Any] | None = None

class NormalizedAward(BaseModel):
    ocds_award_id: str | None
    supplier_ref: str
    value_amount: int | None
    currency: str = "NGN"
    awarded_at: datetime | None
    meta: dict[str, Any] | None = None

class NormalizedContract(BaseModel):
    ocds_contract_id: str | None
    award_ref: str | None     # ocds_award_id
    supplier_ref: str
    agency_ref: str
    value_amount: int | None
    currency: str = "NGN"
    signed_at: datetime | None
    period: dict[str, Any] | None
    status: str | None
    meta: dict[str, Any] | None = None

class NormalizedRelease(BaseModel):
    ocid: str
    parties: dict[str, NormalizedParty]   # ref → party
    tender: NormalizedTender | None
    awards: list[NormalizedAward]
    contracts: list[NormalizedContract]
    skipped: list[str]                    # human-readable skip reasons
```

`agency_ref` / `supplier_ref` are local keys (prefer OCDS party `id`, else slug of name).

### 4.2 Public functions

```python
def unwrap_extraction_payload(payload: dict[str, Any]) -> Any: ...
def normalize_ocds_document(doc: Any) -> list[NormalizedRelease]: ...
def normalize_ocds_release(release: dict[str, Any]) -> NormalizedRelease: ...
def amount_to_kobo(amount: Any) -> int | None: ...
def map_procurement_method(raw: str | None) -> TenderMethod | None: ...

def load_normalized_release(connection: Connection, release: NormalizedRelease) -> LoadResult: ...
```

`LoadResult`: counts inserted/updated + resolved UUID map for tests.

### 4.3 Loader upsert rules (minimal; #35 may tighten)

| Table | Conflict target | On conflict |
|---|---|---|
| `parties` | `(party_type, lower(canonical_name))` | update `aliases`/`identifiers`/`updated_at` (merge jsonb shallow) |
| `tenders` | `ocid` (non-null) | update title/method/value/currency/meta/`updated_at` |
| `awards` | no natural key yet | **insert always** in v1 (dedupe in #35) |
| `contracts` | no natural key yet | **insert always** in v1 (dedupe in #35) |

Document this gap in #35 acceptance criteria.

## 5. Acceptance criteria (testable)

- [ ] `amount_to_kobo(1000.5)` → `100050`; `None` → `None`.
- [ ] `map_procurement_method` covers open/selective/limited/direct; unknown → `None`.
- [ ] Fixture release with buyer + tender + one award + one contract produces expected DTO fields
      (`ocid`, titles, kobo amounts, party names).
- [ ] Release package with two releases → two `NormalizedRelease`s.
- [ ] `unwrap_extraction_payload({"value": {...}})` returns inner object.
- [ ] `load_normalized_release` against Postgres: second call with same `ocid` does not create a
      second tender; party unique holds.
- [ ] Missing agency (no buyer/procuringEntity) → tender not loaded; reason in `skipped`.

## 6. Risks & mitigations

- **Partial OCDS** (title-only rows from portals) — skip incomplete graphs; record `skipped`.
- **Award/contract insert duplication on re-run** — accepted until #35 adds natural keys /
  content hashes.
- **Name-only party identity** — populate `identifiers.ocds_id` aggressively; E6 merges later.
- **Currency non-NGN** — still convert major→minor with ×100 (ISO-like); store currency code as-is.

## 7. Open questions

None blocking. Follow-ups: #34 provenance subjects after load; #35 award/contract idempotency;
HTML non-OCDS adapters as separate specs.
