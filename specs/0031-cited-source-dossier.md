# Spec 0031 — Cited-source component + dossier export (E10.6)

- **Epic / Issue**: E10.6 / #54
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — client-side citation UI + JSON/Markdown dossier download
  from in-page evidence. Archive-byte serving remains deferred (0023).

## 1. Problem

SYSTEM_DESIGN §4.12: every figure cites its source and drills to the archived document;
OSINT-style **cited-sources dossier export**. Citations today are ad-hoc links in scrolly
steps; there is no shared component or export bundle.

## 2. Scope & non-scope

- **In scope**
  - `CitedSource` presentational component (label, optional href, optional note/kind).
  - `Citation` / `Dossier` types + pure `buildDossier`, `dossierToJson`, `dossierToMarkdown`.
  - `downloadTextFile` helper (browser download).
  - Wire `CitedSource` into scrolly step citations; add a compact citation strip on Explore
    detail, Graph detail, Map detail, and Source detail (linking to `/sources` where useful).
  - Story page: **Export dossier** button (JSON + Markdown) from the demo story’s citations.
  - Tests: dossier builders; CitedSource renders link/span; story export control present.
- **Out of scope**
  - MinIO / signed archive URLs.
  - Server-side dossier API.
  - PDF/DOCX export.
  - Admin portal (#102).

## 3. Design

```text
CitedSource  →  consistent citation chip/link
Dossier      →  { title, generated_at, items: Citation[] }
Export       →  download .json / .md (client-only)
```

## 4. Data contracts

```ts
type Citation = {
  id: string;
  label: string;
  href?: string;
  kind?: string;
  note?: string;
};

type Dossier = {
  title: string;
  generated_at: string; // ISO
  demo: boolean;
  items: Citation[];
};
```

## 5. Acceptance criteria (testable)

- [x] `CitedSource` renders label; uses `<a>`/`Link` when `href` set, else `<span>`.
- [x] `buildDossier` collects unique citations by id.
- [x] `dossierToJson` / `dossierToMarkdown` produce non-empty strings including title.
- [x] Story page exposes Export dossier (JSON and Markdown) for the demo story.
- [x] Explore/Graph/Map/Source detail surfaces at least one `CitedSource` toward sources.
- [x] `pnpm --filter @naijaledger/web lint typecheck test` pass.
- [x] No new server endpoints.

## 6. Risks & mitigations

- **Demo dossier treated as evidence pack** — `demo: true` in payload + UI copy.
- **Download blocked in some browsers** — use Blob + temporary object URL.

## 7. Open questions

None blocking.
