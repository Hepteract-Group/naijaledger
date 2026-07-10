# Spec 0025 — Partner data-export endpoints (E9.3)

- **Epic / Issue**: E9.3 / #48
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — v1 uses **ops-managed bearer tokens** from settings
  (constant-time plaintext compare), same public DTOs as E9.1 (no extra PII), keyset-paginated
  NDJSON. Partner onboarding / legal MoUs remain E12.5 `[H]`; this only ships the technical
  export surface. Bulk open-flag export is consciously the same hypothesis surface as public
  `GET /v1/flags`, at larger page size.

## 1. Problem

Newsroom partners need **bulk, machine-friendly dumps** of canonical public-finance rows and open
flags — not just interactive page-sized GETs (`SYSTEM_DESIGN.md` §4.11; ROADMAP E9.3). E9.1’s
`limit≤200` pages are awkward for full corpus sync.

## 2. Scope & non-scope

- **In scope**
  - Authenticated export routes under `/v1/export/...` (GET only):
    - `GET /v1/export/parties`
    - `GET /v1/export/tenders`
    - `GET /v1/export/awards`
    - `GET /v1/export/contracts`
    - `GET /v1/export/flags` — **open flags only** (hypotheses; same as public list)
    - `GET /v1/export/sources` — default approved (query `status` like public API)
  - Auth: `Authorization: Bearer <token>` where tokens are listed in settings
    `api_partner_export_tokens` (comma-separated plaintext secrets in env for v1; compared with
    `hmac.compare_digest`). Missing/invalid → `401`. Empty list → all export routes `401`.
  - Format: **NDJSON** default (`application/x-ndjson`) — one public DTO JSON object per line,
    keyset-paginated (not an unbounded stream). Optional `?format=json` returns
    `{"items":[...],"next_cursor":...|null}`.
  - Cursor pagination: `?cursor=<opaque>` + `?limit=` (default 500, max 2000).
    NDJSON: header `X-Next-Cursor` when more rows exist.
    Cursor = URL-safe encoding of `(created_at ISO, id)` keyset on `(created_at ASC, id ASC)`.
    Tampered/garbage cursor → `422`.
  - **Rate limiting (concrete):**
    - Global E9.2 IP limiter **skips** paths under `/v1/export/` (export has its own budget).
    - Export middleware order: verify bearer → if invalid/missing `401` → else partner limiter
      keyed by `partner:<sha256(token)[:16]>` at `api_partner_export_per_minute` (default **300**).
    - Invalid tokens never consume / receive the partner budget.
  - Reuse public DTOs from E9.1 (no `meta`, identifiers, operator fields).
  - `.env.example` documents `API_PARTNER_EXPORT_TOKENS=` (empty placeholder).
  - Tests covering ACs below.
- **Out of scope**
  - Per-partner DB table / rotation UI / admin portal (follow-up).
  - Hashed-at-rest token store (follow-up; v1 secrets live in env/secret manager).
  - CSV / Parquet / signed S3 dumps.
  - Stories / review_decisions export (still gated by #126 + product).
  - Changing public interactive `/v1` resources.
  - Legal MoU / partner directory (E12.5).

## 3. Design

### 3.1 Invariant

```text
Export = same public DTOs as /v1 (no privilege escalation of fields)
Open flags only
Bearer required
Keyset-paginated NDJSON primary; JSON array secondary
/v1/export exempt from global IP limiter; partner budget after auth
```

### 3.2 Auth

```python
# Settings
api_partner_export_tokens: list[str] = []  # from env CSV
api_partner_export_per_minute: int = 300
```

Constant-time compare against the configured list (`hmac.compare_digest` per candidate).
Tokens are **secrets in env**, not hashed-at-rest in v1.

### 3.3 Keyset cursor

```text
ORDER BY created_at ASC, id ASC
WHERE (created_at, id) > (cursor_ts, cursor_id)
LIMIT :limit
```

Opaque cursor: `base64url(json({"t": iso8601, "i": uuid}))`. Tamper → 422.

### 3.4 Rate limit + wiring

```text
Global rate_limit_middleware:
  if path startswith /v1/export/ → skip (do not apply IP budget)

Export stack (inside routes or thin middleware on /v1/export):
  Authorization Bearer → verify → 401 if fail
  partner take(sha256(token)[:16]) → 429 if over api_partner_export_per_minute
  handler
```

```text
api/auth_partner.py → verify_partner_token / token_fingerprint
api/v1/export.py → routes + Depends(require_partner)
api/export_queries.py → keyset SELECTs → public DTOs
api/rate_limit.py → exempt /v1/export/; optional partner take helper
config.py + .env.example → api_partner_export_*
```

Fingerprint for keys/logs = `sha256(utf8(token)).hexdigest()[:16]` — **never** a raw token
prefix/substring.

### 3.5 OpenAPI

Tag `export` — “Partner bulk export (bearer token required). Flags remain hypotheses.”

## 4. Data contracts / schemas

NDJSON line = one of `PublicParty | PublicTender | PublicAward | PublicContract | PublicFlag |
PublicSource` (same schemas as E9.1).

```http
GET /v1/export/parties?limit=500
Authorization: Bearer <token>
Accept: application/x-ndjson

HTTP/1.1 200
Content-Type: application/x-ndjson
API-Version: 1
X-Next-Cursor: eyJ0IjoiLi4uIiwiaSI6Ii4uLiJ9
```

## 5. Acceptance criteria (testable)

- [x] `GET /v1/export/parties` without `Authorization` → `401`.
- [x] Invalid bearer → `401` on each export route (parametrize parties/flags at minimum).
- [x] Empty `API_PARTNER_EXPORT_TOKENS` → all export routes `401`.
- [x] With configured token → `200` and `Content-Type` includes `ndjson` (default).
- [x] Each NDJSON line parses as JSON object without `meta` / `identifiers` / `added_by`.
- [x] `?format=json` returns `{"items":[...],"next_cursor": ...|null}`.
- [x] Two-page cursor walk returns disjoint ids; second page uses cursor / `X-Next-Cursor`.
- [x] Tampered/garbage `cursor` → `422`.
- [x] `GET /v1/export/flags` never includes non-open flags.
- [x] With partner limit=2, third export request in-window → `429`; a parallel public
      `/v1/parties` IP budget is unaffected by export traffic (export exempt from global limiter).

## 6. Risks & mitigations

- **Token leakage** — treat like secrets; rotation = change env + restart; never log raw tokens
  (fingerprint only).
- **Bulk scrape of hypotheses** — same fields as public flags; OpenAPI warning retained;
  partners still subject to MoU under E12.5.
- **Large responses** — keyset + max 2000; no unbounded single response.

## 7. Open questions

None blocking. Per-partner identity / audit log of who exported what → follow-up when E12.5
lands partner registry.
