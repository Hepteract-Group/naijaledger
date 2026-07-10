# Spec 0010 — Scheduler: Postgres jobs + worker + Make/cron (E3.5)

- **Epic / Issue**: E3.5 / #26
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — orchestrator choice already recorded on #26 (2026-07-07):
  minimal Postgres `jobs` table + worker + cron/Make trigger (not Prefect/Dagster; not Make.com).

## 1. Problem

Fetch today is **manual / batch**: `make fetch-sources` walks all approved sources once. Production needs
**cadence-driven**, **idempotent**, and **resumable** runs so sources with `expected_cadence` are
fetched when due without re-fetching everything, and a crashed worker can continue without
duplicate work.

Derives from `SYSTEM_DESIGN.md` §4.2 (scheduling drives the fetch layer) and the recorded decision:
Postgres job queue + worker process + host cron invoking Make/CLI.

## 2. Scope & non-scope

- **In scope**
  - `jobs` table + Alembic migration.
  - Enqueue logic: approved sources whose cadence says they are **due**.
  - Worker: claim due jobs (`SKIP LOCKED`), run existing fetch path for one source, mark
    succeeded/failed, retry with backoff.
  - CLI + Makefile targets suitable for cron (`jobs-enqueue`, `jobs-work`).
  - Idempotency keys so re-enqueue does not create duplicate active jobs for the same due window.
- **Out of scope**
  - Prefect / Dagster / Make.com / cloud workflow SaaS.
  - Extract / normalize job kinds (follow-up once E5 needs scheduled extract; schema allows
    `kind` extension).
  - Distributed multi-region workers beyond a single-process worker + Postgres locking.
  - Changing `expected_cadence` seed values (already on `sources`).

## 3. Design

### 3.1 Flow

```
cron / operator
  → make jobs-enqueue
       → for each approved source that is due:
            INSERT job (kind=fetch_source, subject_id=source.id, …)
            ON CONFLICT (idempotency_key) DO NOTHING

cron / operator / long-running process
  → make jobs-work   (or naijaledger-jobs work --loop)
       → claim next job: SELECT … FOR UPDATE SKIP LOCKED
       → status=running, locked_by=worker_id, locked_at=now
       → dispatch:
            fetch_source → existing static/scrapling/playwright fetch for that source
       → status=succeeded | failed (attempts++, run_after=now+backoff on retryable fail)
```

### 3.2 Due rule

A source is **due** when all hold:

1. `status = 'approved'`
2. `expected_cadence IS NOT NULL`
3. `last_fetched_at IS NULL` **or** `now() >= last_fetched_at + expected_cadence`

Sources with null cadence are never auto-enqueued (manual `make fetch-sources` still works).

### 3.3 Idempotency

`idempotency_key` unique, format:

```
fetch_source:{source_id}:{due_bucket}
```

`due_bucket` = floor of “due instant” to the cadence window start (UTC), e.g. for weekly cadence
the ISO week of the due time, or more simply:

```
due_bucket = floor_timestamp(coalesce(last_fetched_at, epoch) + expected_cadence)
```

expressed as an ISO-8601 UTC timestamp truncated to seconds. Re-running enqueue in the same window
hits `ON CONFLICT DO NOTHING`. After success, the next window gets a new key when the source is
due again.

### 3.4 Claim / resume

- Claim with `FOR UPDATE SKIP LOCKED` so multiple workers (future) do not double-run.
- `locked_by` = worker id (hostname + pid + uuid fragment).
- **Stale lock reclaim:** if `status='running'` and `locked_at < now() - lock_timeout`
  (default 30 minutes), enqueue/worker may reset to `queued` (or re-claim). Prevents stuck jobs
  after a killed process.
- Failed jobs with `attempts < max_attempts` (default 3) return to `queued` with
  `run_after = now() + backoff` (e.g. 1m, 5m, 15m). Exhausted → `dead`.

### 3.5 Dispatch (v1)

| `kind` | `subject_id` | Action |
|--------|--------------|--------|
| `fetch_source` | `sources.id` | Run the same fetch path as today’s CLI for **that one** source (http / scrapling / playwright + catalog children as already implemented). |

Do **not** reimplement fetch; call into existing `static_fetch_source` /
`scrapling_fetch_source` / `playwright_fetch_source` (or a thin `fetch_source_by_id` wrapper).

## 4. Data contracts / schemas

### 4.1 `jobs`

```
jobs(
  id              uuid pk default gen_random_uuid(),
  kind            text not null,          -- fetch_source (extensible)
  subject_id      uuid not null,          -- e.g. sources.id
  status          text not null,          -- queued|running|succeeded|failed|dead
  idempotency_key text not null unique,
  run_after       timestamptz not null default now(),
  attempts        int not null default 0,
  max_attempts    int not null default 3,
  locked_at       timestamptz null,
  locked_by       text null,
  last_error      text null,
  result          jsonb null,             -- optional summary (fetch_record_id, ok, …)
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  CHECK (status IN ('queued','running','succeeded','failed','dead')),
  CHECK (kind IN ('fetch_source'))        -- widen later for extract_*
)
CREATE INDEX ix_jobs_claim ON jobs (status, run_after) WHERE status IN ('queued','failed');
```

(`failed` rows that are still retryable should be selected with `run_after <= now()`; either keep
them as `queued` after scheduling retry, **or** select `status IN ('queued')` only and always
flip retryable failures back to `queued`. Prefer the latter — simpler claim query.)

### 4.2 Functions (functional)

```python
def list_due_sources(connection, *, now: datetime) -> list[SourceRecord]: ...

def enqueue_due_fetch_jobs(connection, *, now: datetime) -> EnqueueSummary:
    # attempted, inserted, skipped_conflict

def claim_next_job(connection, *, worker_id: str, now: datetime) -> Job | None: ...

def complete_job(connection, job_id: UUID, *, result: dict) -> None: ...

def fail_job(connection, job_id: UUID, *, error: str, now: datetime) -> None:
    # attempts++; if attempts < max_attempts → queued + run_after; else dead

def run_fetch_source_job(connection, job: Job, *, minio..., settings...) -> dict: ...

def work_once(...) -> bool:  # claimed and ran one job; False if idle
def work_loop(..., idle_sleep_s: float = 5.0) -> None: ...
```

### 4.3 CLI / Make

```
naijaledger-jobs enqueue
naijaledger-jobs work [--once | --loop] [--worker-id ID]
```

Makefile:

```
jobs-enqueue: migrate
	cd engine && uv run naijaledger-jobs enqueue

jobs-work:
	cd engine && uv run naijaledger-jobs work --once
```

Cron example (host / Fly machine): `*/15 * * * * cd /app && make jobs-enqueue && make jobs-work`

Settings (optional): `job_lock_timeout_seconds=1800`, `job_max_attempts=3`.

## 5. Acceptance criteria (testable)

- [x] Migration creates `jobs` with unique `idempotency_key` and status/kind CHECKs.
- [x] `list_due_sources`: approved + cadence set + never fetched **or** past cadence; excludes
      retired/proposed and null-cadence.
- [x] `enqueue_due_fetch_jobs` inserts one row per due source; second enqueue in the same due
      window inserts **0** new rows (conflict on idempotency_key).
- [x] `claim_next_job` returns a queued job with `run_after <= now`, sets `running` + lock fields;
      concurrent claim of the same row is impossible under `SKIP LOCKED` (tested with two
      connections or simulated).
- [x] Successful `fetch_source` job → `succeeded` + `result` containing `fetch_record_id` (mock
      fetch OK).
- [x] Failed job with attempts remaining → back to `queued` with future `run_after`; after
      `max_attempts` → `dead`.
- [x] Stale `running` job older than lock timeout is reclaimable to `queued`.
- [x] Unit tests do not require live network (mock per-source fetch).

## 6. Risks & mitigations

- **Thundering herd** — enqueue only **due** sources; worker processes one (or a small batch) at a
  time; catalog child fetches remain capped (`catalog_discovery_max_children`).
- **Stuck running** — lock timeout + reclaim.
- **Duplicate fetches** — unique idempotency key per due window; fetch layer already dedups
  documents by sha256.
- **Cadence null** — skip auto-schedule; document that seeds should set cadence (they already do).

## 7. Open questions

None blocking. Implementation defaults above apply unless revised in the build PR:

- Lock timeout default **30m**; max attempts **3**; backoff **1m / 5m / 15m**.
- Extract job kinds deferred to a follow-up issue when E5 wants scheduled parse.
