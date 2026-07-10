# Spec 0025 — Partner data-export endpoints (E9.3)

- **Epic / Issue**: E9.3 / #48
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — v1 uses **ops-managed bearer tokens** from settings (hashed
  compare), same public DTOs as E9.1 (no extra PII), NDJSON bulk streams. Partner onboarding /
  legal MoUs remain E12.5 `[H]`; this only ships the technical export surface.

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
    `api_partner_export_tokens` (comma-separated plaintext in env for v1; compared in constant
    time). Missing/invalid → `401`.
  - Format: **NDJSON** (`application/x-ndjson`) — one public DTO JSON object per line.
    Optional `?format=json` returns a single JSON array (capped; see below).
  - Cursor pagination for NDJSON: `?cursor=<opaque>` + `?limit=` (default 500, max 2000).
    Response headers: `X-Next-Cursor` when more rows exist; empty/absent when done.
    Cursor = URL-safe encoding of `(created_at ISO, id)` keyset on `(created_at ASC, id ASC)`.
  - JSON array mode: same cursor/limit; body `{"items":[...],"next_cursor":...|null}`.
  - Partner rate limit: separate higher budget when bearer valid
    (`api_partner_export_per_minute`, default 300); unauthenticated `/v1/export` always 401
    (no anonymous bulk).
  - Reuse public DTOs from E9.1 (no `meta`, identifiers, operator fields).
  - Tests: 401 without token; 200 NDJSON with token; cursor advances; flags open-only;
    invalid token 401.
- **Out of scope**
  - Per-partner DB table / rotation UI / admin portal (follow-up).
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
NDJSON primary; JSON array secondary
```

### 3.2 Auth

```python
# Settings
api_partner_export_tokens: list[str] = []  # from env CSV
api_partner_export_per_minute: int = 300
```

`.env.example`: `API_PARTNER_EXPORT_TOKENS=` placeholder (empty = exports disabled → all 401).

Constant-time compare against the configured list (`hmac.compare_digest` per candidate).

### 3.3 Keyset cursor

```text
ORDER BY created_at ASC, id ASC
WHERE (created_at, id) > (cursor_ts, cursor_id)
LIMIT :limit
```

Opaque cursor: `base64url(json({"t": iso8601, "i": uuid}))`. Tamper → 422.

### 3.4 Wiring

```text
api/v1/export.py → routes + bearer dep
api/export_queries.py → keyset SELECTs → public DTOs
api/auth_partner.py → verify_partner_token
rate_limit.py → higher limit when Authorization present AND valid
  (or separate middleware path for /v1/export only)
```

Prefer: `/v1/export/*` uses its own rate-limit key `partner:<token-fingerprint>` with the
partner budget; invalid tokens never get the higher budget (401 before work).

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

- [ ] `GET /v1/export/parties` without `Authorization` → `401`.
- [ ] With configured token → `200` and `Content-Type` includes `ndjson` (default).
- [ ] Each NDJSON line parses as JSON object without `meta` / `identifiers` / `added_by`.
- [ ] Two-page cursor walk returns disjoint ids and second page uses `X-Next-Cursor`.
- [ ] `GET /v1/export/flags` never includes non-open flags.
- [ ] Empty `API_PARTNER_EXPORT_TOKENS` → all export routes `401`.
- [ ] Invalid bearer → `401`.

## 6. Risks & mitigations

- **Token leakage** — treat like secrets; document rotation = change env + restart; never log
  raw tokens (fingerprint only if logging).
- **Bulk scrape of hypotheses** — same as public flags; OpenAPI warning retained.
- **Large responses** — keyset + max 2000; no unbounded dump in one response.

## 7. Open questions

None blocking. Per-partner identity / audit log of who exported what → follow-up when E12.5
lands partner registry.
