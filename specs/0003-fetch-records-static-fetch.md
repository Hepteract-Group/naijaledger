# Spec 0003 — Static fetch + fetch_records

- **Epic / Issue**: E3.2 / #23
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no

## 1. Problem
Every ingestion run must capture raw bytes immutably and record the attempt before any parsing
(P1, `provenance-and-verification.mdc`). The static HTTP fetch path (`fetch_method=http`) is the
first capture implementation and writes evidentiary `fetch_records` rows linked to the WORM archive.

## 2. Scope & non-scope
- In scope: `fetch_records` migration, service insert/read, httpx GET fetcher for `http` sources,
  archive-then-record ordering, update `sources.last_fetched_at` / `last_success_hash` on success.
- Out of scope: Scrapling/Playwright (E3.3), `documents` dedup (E3.4), scheduler (E3.5),
  extraction/parsing (E4).

## 3. Design
1. Validate URL (http/https only; block localhost/link-local per security rules).
2. `httpx` GET with redirects, capture status + headers + body.
3. **Archive** body via `store_raw_bytes` (idempotent by content hash).
4. **Insert** `fetch_records` row (always, success or failure).
5. On `ok` (2xx/3xx with body archived): `record_fetch_success` on the source.

Failed connection: fetch_record with `ok=false`, no archive key.

## 4. Data contracts / schemas

### `fetch_records` table
`id, source_id (FK sources), url, requested_at, status_code, ok, byte_count, sha256, headers jsonb,
error, archive_key, created_at, updated_at`

Index: `(source_id, requested_at DESC)`.

### Functions
```python
def create_fetch_record(...) -> FetchRecord: ...
def get_fetch_record(connection, fetch_id) -> FetchRecord: ...
def static_fetch_source(connection, source, *, http_client, minio_client, bucket, now) -> StaticFetchResult: ...
def run_static_fetch_for_approved_http_sources(connection, ...) -> StaticFetchSummary: ...
```

`StaticFetchResult`: `fetch_record_id, ok, archive_key, content_hash`.

## 5. Acceptance criteria (testable)
- [x] Migration creates `fetch_records` with FK to `sources` and reverses cleanly.
- [x] Successful mocked fetch archives bytes then inserts row with matching `sha256` / `archive_key`.
- [x] Failed fetch inserts row with `ok=false` and no `archive_key`.
- [x] `record_fetch_success` called only on successful fetch.
- [x] CLI / `make fetch-sources` runs against approved `http` sources.

## 6. Risks & mitigations
- Large payloads → defer streaming/chunking to a follow-up; cap not enforced in v1 (monitor byte_count).
- SSRF → shared URL policy blocks private/localhost hosts.

## 7. Open questions
- None blocking.
