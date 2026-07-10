# NaijaLedger — Roadmap (Epics → Issues)

> Derives from `SYSTEM_DESIGN.md`. Each **Epic** becomes a GitHub issue labelled `epic`.
> Each child becomes an issue labelled `story` (or `task`) and references its epic.
> Agents work these via the loop in `AGENTS.md`. Order roughly follows dependency.

Legend: `[H]` = likely needs a human decision (`needs-human`), `[S]` = spec required before build.

---

## E1 — Foundations
- E1.1 Repository bootstrap: LICENSE, README, `.gitignore`, `.env.example`, CODEOWNERS.
- E1.2 CI: lint + typecheck + tests for Python and TS packages.
- E1.3 Dev environment: `docker-compose` (Postgres, MinIO, Neo4j, search).
- E1.4 Monorepo layout decision + skeleton (`/engine` Python, `/web` TS, `/specs`, `/docs`). `[H]`
- E1.5 Agent workflow docs: `AGENTS.md` + `.cursor/rules/*` (loop, spec-driven, functional, safety).
- E1.6 Spec framework: `specs/` structure + `specs/TEMPLATE.md` + example spec. `[S]`
- E1.7 GitHub Project board + labels + issue/PR templates.

## E2 — Source Registry
- E2.1 `sources` schema + migration. `[S]`
- E2.2 Registry CRUD + service functions (functional).
- E2.3 Seed registry with known sources (NOCOPO, Open Treasury, Budget Office, NEITI, OpenStates.ng, CAC BO). `[H]`
- E2.4 Health monitor job (HTTP status, TLS expiry, schema-fingerprint drift) + alerts.
- E2.5 Source-discovery agent (proposal-only; human approves). `[S]`

## E3 — Capture & Archive
- E3.1 MinIO WORM archive: client wrapper, content-hash keying, retention lock. `[S]`
- E3.2 Fetch layer: `httpx` static fetcher + `fetch_records` writer (hash-before-parse).
- E3.3 Scrapling integration for dynamic/brittle portals (adaptive, pause/resume).
- E3.4 `documents` dedup by content hash + archive linkage.
- E3.5 Scheduler wiring (cadence-driven, idempotent, resumable) — **decided:** Postgres `jobs` +
  worker + cron/Make (`specs/0010-scheduler-jobs.md`). `#26`

## E4 — Extraction
- E4.1 **Extraction contract** spec: dual-pass + Magika quarantine + Docling tables — `specs/0009`. `[S]` ✓
- E4.2 **`extract_document` orchestrator** + provenance wiring (in-engine; no PeaDF client for v1).
- E4.3 PDF text/tables via **Docling in-engine**.
- E4.4 XLSX/CSV + JSON parsers → `extractions`.
- E4.5 OCR fallback (**Tesseract in-engine**); vision-LLM last resort (cost-gated).
- E4.x Magika router + quarantine (#87) ✓; `extractions` derivation/confidence schema (#88) ✓.

## E5 — Normalize & Canonical Store
- E5.1 Postgres core schema + migrations (parties/tenders/awards/contracts/payments/budget_lines). `[S]` ✓
- E5.2 OCDS normalizer mapping. `[S]` ✓
- E5.3 Provenance edges wired end-to-end (every datum → document+region). ✓
- E5.4 Idempotent load/upsert with re-run safety. ✓ (OCDS path; awards/contracts via `meta.ocds_*_id`)

## E6 — Entity Resolution & Graph
- E6.1 Deterministic + probabilistic party matching; `merged_into` handling. `[S]` ✓
- E6.2 LLM adjudication for hard matches (human-confirmed). ✓ (stub adjudicator + human confirm; live LLM deferred)
- E6.3 Beneficial-ownership enrichment (CAC PSC / NEITI BO / OpenOwnership). `[H]` access strategy.
- E6.4 Neo4j projection builder (rebuildable from Postgres). → **Memgraph** v1 ✓ (`specs/0016`)

## E7 — Anomaly Engine
- E7.1 Rule framework + evidence output schema (`flags`). `[S]` ✓
- E7.2 Rules: single_bidder, short_window, threshold_hugging, repeat_winner, shared_address, price_outlier, budget_payment_mismatch. `[S]` ✓
- E7.3 Backtest/precision harness on seeded data. `[S]` ✓

## E8 — Intelligence / Agents
- E8.1 Agent runtime + tool interfaces (retrieval over search/vector/graph). `[S]` ✓
- E8.2 Narrative agent (drafts cited stories) + Verification agent (claim→evidence check). `[S]` ✓
- E8.3 Human-review queue (`review_decisions`) gating publication (P3). `[S]` ✓

## E9 — Public API
- E9.1 FastAPI read API over canonical + derived stores. `[S]` ✓
- E9.2 OpenAPI docs + versioning + rate limiting.
- E9.3 Partner data-export endpoints (newsrooms).

## E10 — Frontend / Visualization
- E10.1 Web app skeleton (React + Vite + TS). `[H]` design system.
- E10.2 Scrollytelling narrative framework.
- E10.3 Explorable dashboards (filter/sort/compare) with source drill-down.
- E10.4 Graph viz (Sigma.js / react-force-graph).
- E10.5 3D map (MapLibre + deck.gl): state extrusions by contract volume / anomaly density.
- E10.6 Cited-source component + dossier export.
- E10.x **Internal admin portal** (ops: jobs queue, sources, quarantine, review) — `#102` `[S]` later.

## E11 — Election Module
- E11.1 `polling_units` + `polling_unit_results` + `result_crosschecks` schema + INEC PU seed. `[S][H]`
- E11.2 Offline-first observer capture app (photo + GPS + timestamp + on-device hash). `[S]`
- E11.3 OCR pipeline for EC8A → figures with provenance.
- E11.4 Cross-checks (votes ≤ accredited ≤ registered; EC8A vs IReV vs collation).
- E11.5 Statistical sampling + N-way corroboration backbone. `[H]` methodology sign-off.

## E12 — Cross-cutting
- E12.1 Merkle transparency log + periodic public anchoring. `[S]`
- E12.2 Observability (structured logs, correlation IDs, metrics, alerts).
- E12.3 Security & privacy hardening (secrets, PII minimization, SSRF guards).
- E12.4 Legal/FOI pipeline + pre-publication review workflow. `[H]`
- E12.5 Partnership integrations (BudgIT/OpenStates.ng ingest + credit; media data-partner export). `[H]`
