# Spec 0038 — Public `/v1/stories` read API

- **Epic / Issue**: E10.2 follow-up / #137
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — persistence is a first-class `stories` table;
  #126 (reviewer auth) remains a publish-*write* hardening follow-up, not a
  blocker for the approved-read surface.

## 1. Problem

`/stories` is fixture-only. Without a public API over human-approved narrative
payloads, Stories cannot leave demo mode. Agent `StoryDraft` (claims) is not
the scrolly UI contract (`NarrativeStory`).

## 2. Scope & non-scope

- **In scope**
  - `stories` table storing the scrollytelling document (slug, title, lede,
    steps, next link) keyed by review subject id.
  - On `approve_publish` for `subject_type=story`, materialize from
    `review_decisions.meta.narrative` when present.
  - `enqueue_narrative_for_review` for scrolly payloads.
  - `GET /v1/stories` (paged) + `GET /v1/stories/{id}` +
    `GET /v1/stories/by-slug/{slug}` — published rows only (`demo: false`).
  - Web: live list/detail when API returns items; demo fixtures only when
    empty or fetch error (never mix live + demo).
- **Out of scope**
  - Mapping agent `StoryDraft` claims → scrolly steps.
  - Public write routes; reviewer identity binding (#126).
  - Editorial CMS UI.
  - Un-publishing / soft-delete of published stories (future).

## 3. Design

```text
NarrativeStory document
  → enqueue_narrative_for_review (meta.narrative)
  → human approve_publish
  → upsert stories row (id = subject_id)
  → GET /v1/stories*
  → StoriesIndexPage / StoryPage (live or demo fallback)
```

Agent drafts without `meta.narrative` may still receive review decisions but
do **not** appear on the public Stories API.

## 4. Data contracts / schemas

### Table `stories`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | Same as review `subject_id` |
| slug | TEXT UNIQUE | URL key |
| title, lede | TEXT | |
| steps | JSONB | `StoryStep[]` |
| next_label, next_to | TEXT | CTA |
| review_decision_id | UUID NULL | FK → review_decisions |
| published_at | TIMESTAMPTZ | |
| created_at, updated_at | TIMESTAMPTZ | |

### Public API

```ts
type PublicStory = {
  id: string; // UUID
  slug: string;
  title: string;
  lede: string;
  demo: false;
  steps: StoryStep[];
  next: { label: string; to: string };
  published_at: string; // ISO datetime
};

// GET /v1/stories → Page<PublicStory>
// GET /v1/stories/{id} | /v1/stories/by-slug/{slug} → PublicStory
```

`meta.narrative` on enqueue matches the web `NarrativeStory` shape minus
`demo` (ignored if present).

## 5. Acceptance criteria (testable)

- [x] Migration creates `stories`.
- [x] Approve with `meta.narrative` upserts a public row; approve without it does not.
- [x] List/get return only published stories; 404 for unknown id/slug.
- [x] Slug lookup works; list is ordered by `published_at` desc (slug DESC
  tie-break).
- [x] Web uses live when non-empty; demo fixtures when empty or API error.

## 6. Risks & mitigations

- **Accidental publish of agent drafts** — require `meta.narrative` for
  materialization.
- **Slug collisions** — unique constraint; upsert updates existing slug row.
- **#126** — human reviewer string still required by existing gate; identity
  binding deferred.

## 7. Open questions

- None blocking. Follow-up: unpublish / revise workflow; agent→scrolly mapper.
