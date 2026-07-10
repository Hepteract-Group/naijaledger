# Spec 0024 — OpenAPI hardening, versioning policy, rate limiting (E9.2)

- **Epic / Issue**: E9.2 / #47
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — public read API already ships `/v1`; this hardens docs,
  documents the versioning contract, and adds a default in-process rate limit. Redis-backed
  shared limits can follow when multi-replica prod exists.

## 1. Problem

E9.1 delivered GET `/v1/*` with FastAPI’s default OpenAPI. Partners and the web app need:

1. Clear **OpenAPI** metadata (description of hypotheses vs facts, contact/license, tags).
2. An explicit **versioning policy** so `/v1` stays stable.
3. Basic **rate limiting** so anonymous scrape/abuse does not melt Postgres
   (`SYSTEM_DESIGN.md` §4.11; ROADMAP E9.2).

## 2. Scope & non-scope

- **In scope**
  - Enrich FastAPI OpenAPI: title/description (flags = hypotheses), license (project LICENSE),
    tag descriptions for sources/parties/tenders/awards/contracts/flags.
  - Versioning policy (docs + runtime signals):
    - Path versioning remains the contract (`/v1/...`).
    - Response header `API-Version: 1` on `/v1` routes.
    - Breaking changes require `/v2` (additive fields OK in `/v1`).
    - Document deprecation approach: announce → `Deprecation`/`Sunset` headers → remove in
      next major (no sunset yet).
  - In-process rate limiter middleware (functional):
    - Key: `request.client.host` by default.
    - Honor `X-Forwarded-For` **only when** `api_trust_forwarded_for=true` (default **false**);
      when trusted, use the **leftmost** hop. Deployment contract: the edge proxy **MUST
      overwrite** (not append) `X-Forwarded-For` with the real client IP; if the proxy only
      appends, leave trust disabled.
    - Default: **60 requests / 60 seconds** per key for `/v1/*` (configurable).
    - `/health` and `/docs` / `/openapi.json` / `/redoc` exempt.
    - On exceed: `429` with `Retry-After` (seconds until window reset).
    - Bounded store: expire idle keys; hard cap on tracked keys (evict oldest) to prevent
      memory exhaustion from key churn.
  - Settings: `api_rate_limit_per_minute` (int, default 60), `api_rate_limit_enabled` (bool,
    default true), `api_trust_forwarded_for` (bool, default false),
    `api_rate_limit_max_keys` (int, default 10_000).
  - Set CORS `allow_credentials=False` (public unauthenticated API; closes E9.1 review nit).
  - Middleware order: **CORS outermost**, then versioning header, then rate limit (so `429`
    responses still carry CORS headers and `API-Version`).
  - Tests: OpenAPI contains expected description/tags; rate limit returns 429 after burst;
    `/health` never rate-limited; `API-Version` present on `/v1` responses; spoofed XFF does
    not bypass when trust is off.
- **Out of scope**
  - API keys / partner auth (E9.3 may add export tokens).
  - Redis / shared multi-replica limiter (follow-up when horizontal scale needs it).
  - CDN / edge WAF rules.
  - Partner bulk export (E9.3).
  - Changing resource shapes from E9.1.

## 3. Design

### 3.1 Invariant

```text
/v1 = stable contract (additive-only)
Rate limit = best-effort per process (not a security boundary alone)
Flags remain hypotheses in OpenAPI text
XFF trusted only when explicitly configured
```

### 3.2 OpenAPI

```python
app = FastAPI(
    title="NaijaLedger Public API",
    version=__version__,  # package/semver — NOT the API contract major
    description=PUBLIC_API_DESCRIPTION,  # includes flag hypothesis warning + versioning note
    license_info={"name": "See repository LICENSE"},
    openapi_tags=[...],
)
```

`FastAPI(version=...)` / OpenAPI `info.version` = **engine package version**. The public
**contract** major is signaled separately via path `/v1` and header `API-Version: 1`.

Keep `/docs` and `/redoc` enabled in v1 (public civic API). Optional later: gate behind env.

### 3.3 Versioning

| Rule | Behavior |
|------|----------|
| URL | `/v1/...` only for public resources |
| Additive | New optional fields / new GET routes OK without bump |
| Breaking | Rename/remove field, change semantics, auth requirement → `/v2` |
| Signal | `API-Version: 1` on successful and error `/v1` responses |

Policy text lives in `specs/0024` + short note in OpenAPI description (not a separate ADR unless
humans want one).

### 3.4 Rate limiter

Functional middleware (prefer pure ASGI callable over `BaseHTTPMiddleware` if practical):

```text
request → if path exempt → next
       → key = client_host  (or leftmost XFF iff api_trust_forwarded_for)
       → bucket = take(key)  # fixed window; prune expired; cap max keys
       → if denied → 429 + Retry-After (+ CORS already applied outer)
       → else next
```

Document: with N uvicorn workers, effective capacity ≈ `N × limit`. Acceptable until Redis.

### 3.5 Wiring / middleware order

```text
outermost → CORSMiddleware (allow_credentials=False)
         → api_version_middleware   # sets API-Version on /v1* (including limiter 429s)
         → rate_limit_middleware
         → routes
```

```text
api/app.py → OpenAPI metadata, wire middleware in order above
api/versioning.py → API-Version header middleware
api/rate_limit.py → fixed-window limiter + middleware + key resolution
config.py → api_rate_limit_*, api_trust_forwarded_for
```

## 4. Data contracts / schemas

```python
# Settings
api_rate_limit_enabled: bool = True
api_rate_limit_per_minute: int = 60  # >= 1
api_trust_forwarded_for: bool = False
api_rate_limit_max_keys: int = 10_000

# 429 body (JSON)
{"detail": "rate limit exceeded"}
# Headers: Retry-After: <seconds>
```

No DB migrations.

## 5. Acceptance criteria (testable)

- [x] `GET /openapi.json` includes description text stating flags are hypotheses / not verified
      claims.
- [x] OpenAPI `tags` include at least `sources`, `parties`, `flags`.
- [x] `GET /v1/parties` response includes header `API-Version: 1`.
- [x] With `api_rate_limit_per_minute=5`, the 6th `/v1/parties` from same client within the
      window returns `429` and `Retry-After`.
- [x] A `429` response still includes `access-control-allow-origin` when requested with a
      configured CORS `Origin`.
- [x] `/health` remains `200` after a rate-limit burst on `/v1`.
- [x] Rate limiting can be disabled via `API_RATE_LIMIT_ENABLED=false` (or settings) for tests.
- [x] With default `api_trust_forwarded_for=false`, rotating `X-Forwarded-For` does **not**
      bypass the limit (same underlying client still 429s).
- [x] CORS middleware uses `allow_credentials=False`.

## 6. Risks & mitigations

- **Per-process limits undercount/overcount** — document; Redis follow-up when multi-replica.
- **X-Forwarded-For spoofing** — default off; enable only behind a proxy that overwrites XFF.
- **Unbounded key map** — `api_rate_limit_max_keys` + expiry of idle windows.
- **Docs scraping** — `/docs` exempt so humans can read; abuse of docs is low cost vs DB.

## 7. Open questions

None blocking. Redis shared limiter = follow-up issue when deploying >1 API replica.
