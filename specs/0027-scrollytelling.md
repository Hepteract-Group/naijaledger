# Spec 0027 — Scrollytelling narrative framework (E10.2)

- **Epic / Issue**: E10.2 / #50
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no — fixture-backed framework until a public story API exists;
  publication remains gated by `review_decisions` / #126 (`SYSTEM_DESIGN.md` §4.12).

## 1. Problem

E10.1 shipped the shell and routes; `/stories` is still a placeholder. Progressive disclosure
requires a **scrollytelling narrative framework**: headline → scroll-synced steps with a sticky
visual → CTA toward dashboard/source (`SYSTEM_DESIGN.md` §4.12). Without it, E10.3–E10.6 have
nowhere to embed cited narrative flow.

## 2. Scope & non-scope

- **In scope**
  - Typed `NarrativeStory` document (slug, title, lede, steps, citations, demo flag).
  - Scroll-step framework: Intersection Observer → active step; sticky visual panel synced to
    the active step; progress affordance.
  - Routes: `/stories` (index of available stories) and `/stories/:slug`.
  - One **clearly labelled demo fixture** (illustrative, not a published claim).
  - End-of-story CTA toward Explore / Sources (progressive disclosure handoff).
  - Motion: step enter/highlight + visual crossfade (2–3 intentional motions).
  - Unit tests: story lookup, active-step helper, Stories routes render fixture.
- **Out of scope**
  - Public `/v1/stories` API or reading `review_decisions` (follow-up when #126 + product allow).
  - Live charts/maps/graph (E10.3–E10.5) — steps may use **placeholder visuals** only.
  - Cited-source dossier export (E10.6) — citations render as labels/links stubs.
  - Auto-publishing or treating demo copy as verified fact.
  - New chart/map libraries.

## 3. Design

### 3.1 Progressive disclosure

```text
/stories            → index (headlines)
/stories/:slug      → scrollytelling steps + sticky visual
end CTA             → /explore or /sources (dashboard / raw source later)
```

### 3.2 Layout

Desktop: two-column scrolly — scrolling step copy on one side, **sticky** visual on the other.
Mobile: visual sticky under the header (or stacked above steps); steps scroll beneath.

Active step = step whose root has the highest intersection ratio within a center band
(Intersection Observer). Prefer a pure `selectActiveStep` helper for tests.

### 3.3 Demo vs published

Fixture stories set `demo: true` and the UI shows an explicit banner:
“Illustrative demo — not a published claim.” Real published stories (later) omit the banner
only when served from an approved public API.

### 3.4 Stack

No new runtime dependencies. Native `IntersectionObserver` + existing design tokens.

## 4. Data contracts / schemas

```ts
type StoryCitation = {
  id: string;
  label: string;
  href?: string;
};

type StoryVisual =
  | { kind: "stat"; title: string; value: string; detail?: string }
  | { kind: "quote"; title: string; detail: string }
  | { kind: "placeholder"; title: string; detail?: string };

type StoryStep = {
  id: string;
  headline: string;
  body: string;
  visual: StoryVisual;
  citations: StoryCitation[];
};

type NarrativeStory = {
  slug: string;
  title: string;
  lede: string;
  demo: boolean;
  steps: StoryStep[];
  next: { label: string; to: string };
};
```

Registry: `listStories(): NarrativeStory[]`, `getStory(slug): NarrativeStory | undefined`
(fixture module for v1).

## 5. Acceptance criteria (testable)

- [x] `/stories` lists at least one story with title + link to `/stories/:slug`.
- [x] `/stories/:slug` renders headline, lede, ≥2 scroll steps, and sticky/synced visual.
- [x] Demo stories show an explicit “not a published claim” banner.
- [x] `selectActiveStep` (or equivalent pure helper) picks the highest-ratio intersecting step.
- [x] Unknown slug shows a not-found state with link back to `/stories`.
- [x] End CTA navigates toward Explore or Sources.
- [x] `pnpm --filter @naijaledger/web lint typecheck test` pass.
- [x] No new chart/map/UI-kit dependency.

## 6. Risks & mitigations

- **Readers confuse demo with fact** — persistent demo banner; copy avoids real accusations.
- **a11y / reduced motion** — respect `prefers-reduced-motion` for crossfades.
- **IO flaky in tests** — unit-test pure selection; render tests assert structure, not scroll.

## 7. Open questions

None blocking. Public story API remains a follow-up after reviewer auth (#126).
