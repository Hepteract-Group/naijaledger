# Spec 0007 — Documents dedup by content hash + archive linkage

- **Epic / Issue**: E3.4 / #25
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no

## 1. Problem

`fetch_records` captures every attempt, but extraction needs a stable **`documents`**
artifact keyed by content hash. Without dedup, identical bytes re-fetched across runs
create duplicate logical documents and complicate provenance.

## 2. Scope & non-scope

- In scope: `documents` migration; upsert on successful fetch; format inference from
  Content-Type / URL / source; link `first_fetch_id` + `archive_key`.
- Out of scope: catalog link-discovery (#80), Playwright fetch (#81), extraction (E4),
  backfill job for historical `fetch_records` (follow-up).

## 3. Design

After a successful fetch (`ok`, body archived, `sha256` set):

1. Infer `documents.format` (MIME → extension → `sources.format`).
2. `INSERT` document with unique `sha256`; on conflict, return existing row.
3. Extend `FetchCaptureResult` with `document_id` when a document exists.

```
fetch → archive → fetch_record → upsert documents (by sha256)
```

## 4. Data contracts

### `documents` table

`id, source_id (FK), first_fetch_id (FK fetch_records), sha256 (unique), format,
archive_key, title, published_at, meta jsonb, created_at, updated_at`

### Functions

```python
def infer_document_format(
    *, url: str, content_type: str | None, source_format: SourceFormat
) -> SourceFormat: ...

def upsert_document_from_fetch(connection, *, source_id, first_fetch_id, sha256,
    archive_key, format, title=None, meta=None) -> DocumentUpsertResult: ...
```

`DocumentUpsertResult`: `document_id`, `created` (bool).

## 5. Acceptance criteria

- [x] Migration creates `documents` with unique `sha256` and FKs; reverses cleanly.
- [x] Successful fetch creates one `documents` row linked to `fetch_records.id`.
- [x] Re-fetch of identical content returns same `document_id` (`created=false`).
- [x] Failed fetch does not create a document.
- [x] Format inferred from Content-Type when clear; falls back to URL extension then source format.

## 6. Risks & mitigations

- **Cross-source same hash** — global `sha256` unique; `source_id` reflects first discoverer (v1).
- **HTML shell vs real data** — document exists even if content is thin; quality gates are later.

## 7. Open questions

- Backfill existing successful `fetch_records` into `documents`? (defer)
