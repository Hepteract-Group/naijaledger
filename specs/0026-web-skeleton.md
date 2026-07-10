# Spec 0026 — Web app skeleton + design system (E10.1)

- **Epic / Issue**: E10.1 / #49
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: resolved — custom tokens; light+dark; elegant fonts;
  African-inspired palette (recorded on #49).

## 1. Problem

The `/web` package is a Vite/React health-check stub. E10 needs a **product skeleton**:
routing, brand shell, design tokens, and a typed path to the E9 `/v1` API so later
scrollytelling/dashboards/viz can land without re-plumbing (`SYSTEM_DESIGN.md` §4.12).

## 2. Scope & non-scope

- **In scope**
  - Design tokens (CSS variables): light default + dark (`data-theme` + `prefers-color-scheme`).
  - African-inspired palette: forest green, adire indigo, cowrie gold (not purple SaaS /
    cream-terracotta cliché).
  - Typography: elegant serif display + refined sans body (self-hosted via `@fontsource`).
  - App shell: header with **NaijaLedger** brand-first, nav (Home / Explore / Stories /
    Sources), theme toggle, footer.
  - React Router routes + placeholder pages for Explore / Stories / Sources.
  - Home: one-composition hero (brand, headline, lede, CTA) — no dashboard clutter.
  - API client helper + `GET /v1/parties` smoke on Explore (empty-state OK).
  - Keep existing `/health` check (dev/status page or footer indicator).
  - Tests: theme toggle sets `data-theme`; parties fetch mocked; router renders Home.
- **Out of scope**
  - Scrollytelling (E10.2), dashboards (E10.3), graph (E10.4), map (E10.5), dossier (E10.6).
  - Admin portal (#102).
  - Auth / login.
  - Component library (Radix/shadcn) — deferred unless a later story needs it.

## 3. Design

### 3.1 Tokens (sketch)

| Token | Light | Dark |
|-------|-------|------|
| `--bg` | leaf-tinted off-white | deep indigo-green |
| `--ink` | near-black green | soft mint-white |
| `--accent` | forest green | brighter leaf |
| `--gold` | cowrie gold | warm gold |
| `--muted` | muted green-gray | muted sage |

Fonts: **Fraunces** (display) + **Source Sans 3** (body/UI).

### 3.2 Routes

| Path | Page |
|------|------|
| `/` | Home hero |
| `/explore` | Parties list smoke + empty/error states |
| `/stories` | Placeholder |
| `/sources` | Placeholder |
| `/status` | Engine health (existing check) |

### 3.3 Stack adds

- `react-router-dom`
- `@fontsource/fraunces`, `@fontsource/source-sans-3`

Functional components only.

## 4. Acceptance criteria (testable)

- [x] Light is default; toggling theme sets `data-theme="dark"| "light"` on `<html>`.
- [x] Home shows brand **NaijaLedger** as hero-level signal (not only nav text).
- [x] Nav links route to Explore / Stories / Sources without full reload.
- [x] Explore calls `/v1/parties` (via proxied `/api`) and renders list or empty/error.
- [x] `pnpm --filter @naijaledger/web lint typecheck test` pass.
- [x] No new UI kit dependency beyond fonts + router.

## 5. Risks & mitigations

- **Generic AI look** — locked palette/fonts from human decision; avoid Inter/purple.
- **API down in dev** — Explore shows reachable error; Status page documents `make dev-engine`.

## 6. Open questions

None — design decisions recorded on #49.
