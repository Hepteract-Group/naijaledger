# Spec 0033 — Extract → normalize → load jobs (post-fetch pipeline)

- **Epic / Issue**: E3/E4/E5 follow-up / #154
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — extends `jobs.kind` as anticipated by `specs/0010`.

## 1. Problem

`jobs` only runs `fetch_source`. Explore finance rows are loaded via an Ekiti-only CLI
(`make portal-load-ekiti`). Production needs a **source-driven** chain: archive a document,
then adapt → OCDS normalize → idempotent load — without hardcoding the make target as the
primary path.

## 2. Scope & non-scope

- **In scope**
  - Job kind `normalize_load` with `subject_id = documents.id`.
  - Adapter registry keyed by **source URL** (v1: Ekiti HTML table; OCDS JSON documents when
    `format=json` and payload is a release/package).
  - After successful `fetch_source`, enqueue `normalize_load` for the archived document when an
    adapter applies.
  - Worker dispatch for `normalize_load` (MinIO bytes → adapter → extraction + load).
  - Idempotency: `normalize_load:{document_id}:{adapter_id}:{method_version}`.
  - Backfill: enqueue from CLI for a document or latest HTML doc of a source URL.
  - Keep `make portal-load-ekiti` as a thin ops wrapper (fetch + enqueue + work).
- **Out of scope**
  - Generic HTML for all state portals (new adapters as separate stories).
  - PDF/XLSX table → finance (Lagos/Jigawa) — later adapters.
  - Geo state/LGA/year facets (#151).
  - Changing Magika `extract_document` into a separate job kind (adapter path writes
    `extractions` directly for structured OCDS packages).

## 3. Design

```text
fetch_source (ok, document_id)
  → if adapter_for(source.url, document.format):
       enqueue normalize_load(document_id)

normalize_load
  → fetch_raw_bytes(archive_key)
  → adapter.to_ocds_package(bytes, max_rows)
  → create_extraction(payload=package)
  → normalize_ocds_document → load_normalized_release (+ provenance)
```

No adapter → job completes with `{skipped: true, reason: "no_adapter"}` (not a failure).

## 4. Data contracts

```python
JobKind = Literal["fetch_source", "normalize_load"]

# Adapter registry entry (conceptual)
AdapterSpec(
  adapter_id: str,           # e.g. "ekiti-html-table"
  method_version: str,       # e.g. "ekiti-html-table-1"
  formats: frozenset[str],   # {"html"} | {"json"}
  to_package: (bytes, max_rows?) -> dict  # OCDS release package
)
```

Settings: `normalize_load_max_rows` (default 100).

## 5. Acceptance criteria

- [x] `normalize_load` job loads Ekiti fixture HTML into parties/tenders (idempotent on ocid).
- [x] Successful `fetch_source` for an adapted source enqueues `normalize_load` (idempotent key).
- [x] Source without adapter: fetch still succeeds; no normalize job (or skipped if forced).
- [x] Worker dispatches both job kinds; unsupported kind still fails clearly.
- [x] Unit tests fixture/DB only for load path; fetch enqueue mocked where needed.
- [x] Spec updated; `portal-load-ekiti` remains a wrapper, not the only path.

## 6. Risks & mitigations

- **Large HTML / many rows** — `normalize_load_max_rows` cap.
- **Adapter drift** — versioned `method_version` in idempotency key so schema bumps re-run.
- **Double load from CLI + jobs** — upserts are idempotent on ocid.

## 7. Open questions

None blocking. Adamawa/Kaduna adapters are follow-up stories.
