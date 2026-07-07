# Spec 0002 — MinIO WORM archive

- **Epic / Issue**: E3.1 / #22
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no (design doc + human brief already chose self-hosted MinIO)

## 1. Problem
NaijaLedger must preserve raw source bytes immutably before any parsing (P1). Government
transparency portals rot or get taken down; the WORM archive is the evidentiary bedrock
(`SYSTEM_DESIGN.md` §4.3). We need a small Python wrapper around MinIO that enforces
content-hash keying and write-once semantics.

## 2. Scope & non-scope
- In scope: MinIO client factory, bucket bootstrap (object locking enabled), `sha256/<hash>`
  object keys, idempotent put (never overwrite), retention lock on new objects, read-by-key.
- Out of scope: `fetch_records` table/writer (E3.2), `documents` dedup (E3.4), mirroring/IPFS,
  production IAM beyond dev credentials in `.env.example`.

## 3. Design
Functional module `naijaledger.archive.storage`:
1. Hash incoming bytes with SHA-256.
2. Derive key `sha256/<hexdigest>`.
3. If object exists → return existing metadata (`created=false`).
4. Else `put_object` with COMPLIANCE retention until `now + MINIO_RETENTION_DAYS`.
5. Bucket created on first use with `object_lock=True` if missing.

Settings from env (`MINIO_ENDPOINT`, keys, bucket, `MINIO_RETENTION_DAYS` default 3650).

## 4. Data contracts / schemas

```python
class ArchiveStoreResult(TypedDict):
    archive_key: str       # e.g. sha256/ab12...
    content_hash: str      # hex sha256 of bytes
    byte_count: int
    created: bool          # False when object already existed (idempotent)

def content_hash(data: bytes) -> str: ...
def archive_object_key(content_hash: str) -> str: ...
def ensure_archive_bucket(client: Minio, bucket: str, *, retention_days: int) -> None: ...
def store_raw_bytes(client: Minio, bucket: str, data: bytes, *, content_type: str) -> ArchiveStoreResult: ...
def fetch_raw_bytes(client: Minio, bucket: str, archive_key: str) -> bytes: ...
def object_exists(client: Minio, bucket: str, archive_key: str) -> bool: ...
```

`archive_key` in `fetch_records` / `documents` (data-model.md) references the MinIO object key above.

## 5. Acceptance criteria (testable)
- [x] `archive_object_key` returns `sha256/<hash>` for a known digest.
- [x] `store_raw_bytes` uploads once; second call with same bytes returns `created=false` and same key.
- [x] `fetch_raw_bytes` returns identical bytes after store.
- [x] Bucket bootstrap enables object locking (new buckets only).
- [x] Integration test runs against local MinIO when reachable; skipped otherwise.

## 6. Risks & mitigations
- Existing dev MinIO volume without object-lock bucket → wipe volume or use fresh bucket name;
  `ensure_archive_bucket` only sets lock at creation time.
- Retention lock prevents deletes → intentional for WORM; dev uses configurable shorter retention if needed.
- Hash collision → treated as same object (SHA-256).

## 7. Open questions
- None blocking. (Multi-region mirror deferred.)
