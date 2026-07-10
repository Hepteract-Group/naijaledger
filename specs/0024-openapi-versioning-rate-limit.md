# Spec 0024 — OpenAPI hardening, versioning policy, rate limiting (E9.2)

- **Epic / Issue**: E9.2 / #47
- **Status**: Draft
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
    - Key: client IP (`X-Forwarded-For` first hop if present, else `request.client.host`).
    - Default: **60 requests / 60 seconds** per IP for `/v1/*` (configurable).
    - `/health` and `/docs` / `/openapi.json` / `/redoc` exempt.
    - On exceed: `429` with `Retry-After` (seconds until window reset).
  - Settings: `api_rate_limit_per_minute` (int, default 60), `api_rate_limit_enabled` (bool,
    default true). Tests can disable via override/env.
  - Set CORS `allow_credentials=False` (public unauthenticated API; closes E9.1 review nit).
  - Tests: OpenAPI contains expected description/tags; rate limit returns 429 after burst;
    `/health` never rate-limited; `API-Version` present on `/v1` responses.
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
```

### 3.2 OpenAPI

```python
app = FastAPI(
    title="NaijaLedger Public API",
    version=__version__,
    description=PUBLIC_API_DESCRIPTION,  # includes flag hypothesis warning
    license_info={"name": "See repository LICENSE"},
    openapi_tags=[...],
)
```

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

Functional middleware (no classes beyond what Starlette requires for `BaseHTTPMiddleware` —
prefer pure ASGI middleware function if practical):

```text
request → if path exempt → next
       → bucket = take(ip)
       → if denied → 429 + Retry-After
       → else next (+ API-Version if /v1)
```

Token bucket or fixed window is fine; **fixed window per IP** is enough for v1.

Document: with N uvicorn workers, effective capacity ≈ `N × limit`. Acceptable until Redis.

### 3.5 Wiring

```text
api/app.py → OpenAPI metadata, CORS credentials=False, middleware order
api/versioning.py → API-Version header helper / middleware
api/rate_limit.py → fixed-window limiter + middleware
config.py → api_rate_limit_* settings
```

## 4. Data contracts / schemas

```python
# Settings
api_rate_limit_enabled: bool = True
api_rate_limit_per_minute: int = 60  # >= 1

# 429 body (JSON)
{"detail": "rate limit exceeded"}
# Headers: Retry-After: <seconds>
```

No DB migrations.

## 5. Acceptance criteria (testable)

- [ ] `GET /openapi.json` includes description text stating flags are hypotheses / not verified
      claims.
- [ ] OpenAPI `tags` include at least `sources`, `parties`, `flags`.
- [ ] `GET /v1/parties` response includes header `API-Version: 1`.
- [ ] With `api_rate_limit_per_minute=5`, the 6th `/v1/parties` from same client within the
      window returns `429` and `Retry-After`.
- [ ] `/health` remains `200` after a rate-limit burst on `/v1`.
- [ ] Rate limiting can be disabled via `API_RATE_LIMIT_ENABLED=false` (or settings) for tests.
- [ ] CORS middleware uses `allow_credentials=False`.

## 6. Risks & mitigations

- **Per-process limits undercount/overcount** — document; Redis follow-up when multi-replica.
- **X-Forwarded-For spoofing** — trust only behind a known reverse proxy; document that prod
  must strip/overwrite client-supplied XFF at the edge (same as most apps).
- **Docs scraping** — `/docs` exempt so humans can read; abuse of docs is low cost vs DB.

## 7. Open questions

None blocking. Redis shared limiter = follow-up issue when deploying >1 API replica.
