# Spec 0004 — Scrapling fetch integration

- **Epic / Issue**: E3.3 / #24
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no

## 1. Problem
State procurement portals and CAC BO use dynamic/brittle HTML and light anti-bot measures.
Static `httpx` is insufficient; Scrapling provides adaptive fetch with browser impersonation
(`SYSTEM_DESIGN.md` §4.2).

## 2. Scope & non-scope
- In scope: Scrapling `Fetcher` tier (curl_cffi + stealth headers) for `fetch_method=scrapling`
  sources; same archive-then-`fetch_records` path as E3.2; CLI batch runner.
- Out of scope: StealthyFetcher/Playwright tier (escalation follow-up), Scrapling Spider
  pause/resume checkpoints, multi-page crawls, selector persistence (needed at extraction time).

## 3. Design
1. `fetch_url_with_scrapling(url)` → status, body bytes, headers (or error).
2. Reuse `persist_fetch_capture` from `fetch/capture.py`.
3. `run_scrapling_fetch_for_approved_scrapling_sources` filters approved scrapling sources.
4. `naijaledger-fetch` CLI runs **both** http and scrapling batches.

Settings: `scrapling_timeout`, `scrapling_impersonate` (default `chrome`), `scrapling_stealthy_headers`.

## 4. Data contracts / schemas

```python
class ScraplingPageResult(TypedDict):
    status_code: int | None
    body: bytes | None
    headers: dict[str, str] | None
    error: str | None

def fetch_url_with_scrapling(url: str, *, settings: Settings) -> ScraplingPageResult: ...
def scrapling_fetch_source(connection, source, *, minio_client, bucket, ...) -> FetchCaptureResult: ...
```

## 5. Acceptance criteria (testable)
- [x] Scrapling fetch archives bytes and inserts `fetch_records` before any parsing.
- [x] Failed scrapling fetch inserts `ok=false` row without archive key.
- [x] Only `fetch_method=scrapling` sources use scrapling path.
- [x] CLI reports scrapling batch summary alongside http batch.
- [x] Unit tests mock scrapling fetch; no live network in CI.

## 6. Risks & mitigations
- Playwright not installed in CI → use Fetcher tier only (no browser deps required).
- Heavy optional dep → `scrapling[fetchers]` pinned in pyproject; document in README if needed.
- Source DNS/availability → recorded as failed fetch; health monitor tracks separately.

## 7. Open questions
- When to escalate to StealthyFetcher per source? Deferred (config flag follow-up).
