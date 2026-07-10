# NaijaLedger — System Design

> Status: **Draft v0.1** · Owner: Architecture · Audience: contributors & AI agents
> This is the canonical design document. Specs and issues derive from it. If code and this
> document disagree, either the code is wrong or this document is stale — open an issue.

---

## 1. Purpose & scope

**NaijaLedger** is an open, civic-accountability data platform for Nigeria. It exists to make public
information **undeniable, durable, and legible** to ordinary citizens, journalists, and courts.

It has two initial product surfaces that share one engine:

1. **Public-finance transparency** (always-on): ingest budgets, procurement/contracting, and
   payment data; resolve the entities involved; connect the dots into a graph; surface red flags;
   and tell the story visually with every claim traceable to a source document.
2. **Election-results verification** (episodic, high-intensity around an election): capture
   polling-unit result sheets at source, extract the figures, cross-check them against official
   portals, and preserve a tamper-evident record.

### Guiding truth (the "Open Treasury lesson")

Government transparency sources **rot**. Nigeria's Open Treasury Portal ran with an expired TLS
certificate for ~9 months and is intermittently unreachable. Therefore NaijaLedger's first job is not
analysis — it is **preservation**: capture-and-archive every source the moment we can reach it, so
the record survives neglect, takedown, or revision.

### Non-goals (explicitly out of scope)

- NaijaLedger is **not** an anonymous/clandestine or evasion tool. It is a lawful, public,
  nonpartisan accountability platform. Openness is the security model, not secrecy.
- NaijaLedger does **not** publish unverified accusations. Every published claim links to source
  evidence and passes human review.
- NaijaLedger does **not** store personal data it does not need, and never leaks user data.
- NaijaLedger is not affiliated with any political party or candidate.

---

## 2. Design principles

| # | Principle | Consequence in the architecture |
|---|-----------|--------------------------------|
| P1 | **Preservation-first** | Raw capture is archived (write-once + content hash) *before* any parsing. |
| P2 | **Provenance everywhere** | Every extracted datum links to `source_file + page + region` and a fetch record. |
| P3 | **Human-in-the-loop for publication** | AI proposes; a human verifies before anything is published as fact. |
| P4 | **Open by default** | Code, methodology, and (where lawful) data are public. Secrets and PII are not. |
| P5 | **Resilience over convenience** | Prefer self-hostable, open components; mirror data; avoid single points of failure/lock-in. |
| P6 | **Canonical store, derived indexes** | Postgres is the source of truth; graph/search/vector are rebuildable projections. |
| P7 | **Nonpartisan & lawful** | Framing, data handling, and partnerships are built for court/press credibility. |
| P8 | **Idempotent & resumable** | Every pipeline stage can re-run safely and resume after failure. |

---

## 3. High-level architecture

```
                          ┌───────────────────────────────────────────────────────────┐
                          │                      NAIJALEDGER ENGINE                          │
                          │                                                             │
  Sources                 │   ┌────────────┐   ┌──────────────┐   ┌────────────────┐   │
  (gov portals,           │   │  Source    │   │   Fetch /    │   │  Raw Archive   │   │
   PDFs, XLSX,   ─────────┼──►│  Registry  ├──►│   Capture    ├──►│ (WORM + hash)  │   │
   JSON, HTML,            │   └────────────┘   └──────────────┘   └───────┬────────┘   │
   EC8A photos)           │                                               │            │
                          │   ┌────────────────────────────────────────┐  │            │
                          │   │            Extraction layer             │◄─┘            │
                          │   │  PDF (Docling), tables, XLSX, JSON, OCR  │               │
                          │   └───────────────────┬─────────────────────┘               │
                          │                       ▼                                       │
                          │   ┌──────────────┐   ┌────────────────┐   ┌──────────────┐   │
                          │   │ Normalizer   │──►│ Entity         │──►│  Postgres    │   │
                          │   │ (OCDS/schema)│   │ Resolution     │   │ (canonical)  │   │
                          │   └──────────────┘   └────────────────┘   └──────┬───────┘   │
                          │                                                  │           │
                          │        ┌────────────┬───────────────┬───────────┤           │
                          │        ▼            ▼               ▼            ▼           │
                          │   ┌─────────┐  ┌─────────┐   ┌───────────┐  ┌──────────┐     │
                          │   │Memgraph │  │ Search  │   │  Vector   │  │ Anomaly/ │     │
                          │   │ (graph) │  │ index   │   │  store    │  │ red-flag │     │
                          │   └────┬────┘  └────┬────┘   └─────┬─────┘  └────┬─────┘     │
                          │        └───────────┴───────┬───────┴────────────┘           │
                          │                            ▼                                 │
                          │                   ┌─────────────────┐                        │
                          │                   │  Intelligence   │  (agents: discover,    │
                          │                   │  / Agent layer  │   extract, resolve,    │
                          │                   └────────┬────────┘   flag, narrate)       │
                          │                            ▼                                 │
                          │                   ┌─────────────────┐                        │
                          │                   │   Public API    │                        │
                          └───────────────────┴────────┬────────┴────────────────────────┘
                                                        ▼
                     ┌──────────────────────────────────────────────────────────────┐
                     │  Frontend: scrollytelling narratives · explorable dashboards ·  │
                     │  graph viz · 3D maps (MapLibre + deck.gl) · every figure cites  │
                     │  its source and drills down to the original document.           │
                     └──────────────────────────────────────────────────────────────┘
```

The **election module** reuses this exact pipeline: EC8A photo is a "source", capture→archive→
extract(OCR)→normalize→cross-check→tamper-evident log→public dashboard.

---

## 4. Component design

### 4.1 Source Registry
The backbone. A catalog row per source with:
`id, name, jurisdiction (federal/state/LGA), category (budget|procurement|payments|election|company),
url, fetch_method (http|scrapling|playwright|api|manual), format (pdf|xlsx|json|csv|html),
expected_cadence, last_fetched_at, last_success_hash, schema_fingerprint, health_status,
reliability_score, provenance_notes, added_by, approved_by`.

Responsibilities:
- **Auto-discovery**: crawler + LLM classifier *proposes* new sources → human approves into registry.
- **Health monitoring**: detect outages, TLS expiry, schema drift. (This alone would have logged
  the 9-month Open Treasury TLS lapse — itself a publishable accountability signal.)
- **Scheduling**: drives the fetch layer by cadence.

### 4.2 Fetch / Capture layer
- Static files (PDF/XLSX/JSON/CSV): `httpx` (async, simple, fast).
- Dynamic/brittle/anti-bot HTML portals: **Scrapling** (BSD-3) — adaptive element relocation for
  redesign-prone gov sites, anti-bot bypass, spiders with pause/resume checkpoints, dev cache mode.
- Last resort for JS-heavy flows: Playwright.
- **Every fetch** writes a `fetch_record` (url, ts, status, bytes, sha256, headers) and streams the
  raw bytes straight to the archive **before** parsing.
- Respect robots.txt/ToS; legal workstream owns FOI-based acquisition for closed sources.

### 4.3 Raw Archive (WORM)
- Self-hosted **MinIO** (S3-compatible), objects keyed by content hash (`sha256/<hash>`).
- Write-once semantics + retention lock. Never mutated. This is the evidentiary bedrock and the
  censorship-resistance layer (mirrorable to multiple hosts/IPFS).

### 4.4 Extraction layer
Layered, deterministic-first (see `specs/0009-extraction-contract.md`):
1. **Content-type sniff** → **Magika**; quarantine on low confidence or declared/sniffed mismatch.
2. **PDF text + tables** → **Docling** in-engine (layout + TableFormer) with page/bbox provenance.
3. **Scanned/garbled PDFs** → OCR (**Tesseract** in-engine), then vision-LLM only as a last resort
   (cost-gated).
4. **XLSX/CSV** → `openpyxl` / stdlib csv.
5. **JSON/API** → schema-validated direct ingest.
- Contract: functional `extract_document(document, bytes) → ExtractionOutcome` with
  `derivation` (`extracted|inferred|ambiguous`) + `confidence`, persisted to `extractions` /
  `provenance_edges`.
- Every extracted value retains provenance (P2). Hosted PeaDF extract is **not** on the v1 path.

### 4.5 Normalizer
- Public-finance records → **Open Contracting Data Standard (OCDS)** where applicable; budgets/
  payments to internal canonical schemas aligned to OCDS concepts (parties, tender, award, contract,
  transaction).
- Election records → a canonical `polling_unit_result` schema.

### 4.6 Entity Resolution
- Deduplicate/merge companies, people, agencies across sources ("ABC Ltd" == "A.B.C. Limited").
- Deterministic rules + probabilistic matching + LLM adjudication for hard cases (human-confirmed).
- Enrichment from beneficial-ownership registers (CAC PSC register, NEITI BO register,
  OpenOwnership/OpenCorporates) to link contractors → owners → officials.

### 4.7 Canonical store — PostgreSQL
- Source of truth. JSONB for semi-structured payloads + relational core + full-text.
- Holds: sources, fetch_records, documents, extractions, parties, contracts/awards, payments,
  polling_unit_results, provenance edges, review/verification state.

### 4.8 Derived indexes (rebuildable from Postgres)
- **Neo4j / Memgraph** (self-hosted) — relationship graph projection rebuildable from Postgres.
  **v1 choice: Memgraph** (docker-compose; Cypher/Bolt). See `specs/0016-graph-projection.md`.
  Example patterns: `(:Company)-[:SUPPLIED]->(:Contract)<-[:CONTRACTED]-(:Agency)`.
- **Search** — OpenSearch or Postgres FTS.
- **Vector** — pgvector/Qdrant for semantic search + agent retrieval.

### 4.9 Anomaly / red-flag engine
Computable indicators (Open Contracting Partnership / World Bank methodology):
single-bidder awards, abnormally short bidding windows, contracts priced just under approval
thresholds, repeat winners, shared address/directors, price outliers vs comparable contracts,
budget-vs-payment mismatches. Outputs *flags with evidence*, never verdicts.

### 4.10 Intelligence / Agent layer
Narrow, composable agents — **AI proposes, humans dispose** (P3):
- **Source-discovery agent** → proposes new registry entries.
- **Extraction agent** → handles messy-PDF fallback.
- **Entity-resolution agent** → adjudicates hard matches.
- **Anomaly agent** → runs/interprets red-flag rules.
- **Narrative agent** → drafts human-readable, cited stories from flagged patterns.
- **Verification agent** → checks that every drafted claim maps to source evidence before it can be
  queued for human publication review.

### 4.11 Public API
- Read API over canonical + derived stores; serves the frontend and third parties (e.g. partner
  newsrooms). Stable, versioned, documented (OpenAPI).

### 4.12 Frontend / Visualization
Progressive disclosure: **headline → scrollytelling narrative → explorable dashboard → raw source.**
- Charts: ECharts / Observable Plot.
- Graph viz: Sigma.js / react-force-graph.
- Maps incl. **3D**: **MapLibre GL + deck.gl** (e.g. 3D extrusions per state by contract volume /
  anomaly density; time animation). UX inspiration (not dependencies) from the globalthreatmap OSINT
  pattern: dark theme, clustering, heatmap, click-to-drill, cited-sources dossier export.
- Every figure cites its source and drills to the original archived document.

### 4.13 Election module (episodic)
- Offline-first observer capture app: photograph **EC8A**, attach GPS + trusted timestamp, hash on
  device at capture, queue, sync when connectivity returns.
- N-way corroboration + statistically representative sampling (YIAGA "Watching the Vote" style) as
  the credible backbone; census-scale crowd capture layered on top later.
- Cross-checks: votes cast ≤ accredited (BVAS) ≤ registered; captured EC8A vs IReV upload vs final
  collation. Divergence is the 2023 failure mode, now provable.
- Tamper-evident log (see §5.2). Partner with accredited observer orgs for legal standing.

---

## 5. Cross-cutting concerns

### 5.1 Provenance model
Every published number answers: *which document, which page/region, fetched when, from where, hashed
to what, extracted by which method/version, verified by whom.* Stored as first-class edges.

### 5.2 Tamper-evidence
- Hash every artifact at capture; append hashes to a **Merkle transparency log** (Certificate-
  Transparency style). Periodically anchor the tree root publicly. Guarantees no artifact — including
  our own — was silently altered after the fact.

### 5.3 Security & privacy
- No secrets in the repo; `.env` only, secret manager in prod.
- Minimize PII (observers/tipsters); encrypt at rest; strict access controls. Do not repeat the
  government portal's data-leak failure.
- SSRF guards on any URL-fetching endpoints (cf. PeaDF `extract-content` blocked-host pattern).

### 5.4 Observability
- Structured logs with correlation IDs across services; metrics on fetch health, extraction success,
  review throughput; alerting on source outages/schema drift.

### 5.5 Legal & compliance (built-in from day one)
- Register/operate under **Hepteract Group** (UK) umbrella; consider a Nigerian legal entity.
- Pre-publication legal review; defamation risk managed by evidence-linking.
- **FOI Act 2011** request pipeline for closed sources (legal partner owns).
- Media partnerships (OCCRP/ICIJ "data partner" model) — partners bring reach and, by raising the
  project's public profile, protection. Candidate partners: Premium Times, ICIR, FIJ, Dataphyte.
- Coalition/leverage: consume & credit **BudgIT/OpenStates.ng**, Connected Development (Follow The
  Money), Open Contracting Partnership; contribute back; offer the graph/anomaly layer they lack.

---

## 6. Technology stack (hybrid)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Ingestion / extraction / AI | **Python 3.11+** | Best scraping/PDF/ML ecosystem. |
| Fetching | httpx, **Scrapling**, Playwright | Static → adaptive → JS-heavy. |
| PDF | **Docling** (in-engine); Tesseract OCR fallback | Layout + tables + bbox provenance; no external convert hop. |
| Canonical DB | **PostgreSQL** (+ pgvector) | Boring, bulletproof source of truth. |
| Graph | **Memgraph** | Relationship analysis (Cypher/Bolt). Decided — see docker-compose / `specs/0016`. |
| Object store | **MinIO** | Self-hosted WORM archive. |
| Search | OpenSearch / Postgres FTS | Query + retrieval. |
| Orchestration | **Postgres `jobs` + worker + cron/Make** (v1) | Decided #26; Prefect/Dagster later if needed. |
| API | FastAPI | Typed Python API. |
| Frontend | **TypeScript + React (Vite)** | Rich viz; consistent with PeaDF conventions. |
| Maps/Viz | MapLibre GL, deck.gl, ECharts, Sigma.js | Open, no lock-in, 3D-capable. |

**Functional code only** (project rule): no classes unless a framework requires them.

---

## 7. Data model (sketch — full detail in `data-model.md`)

Core entities: `Source`, `FetchRecord`, `Document`, `Extraction`, `Party (Company|Person|Agency)`,
`Tender`, `Award`, `Contract`, `Payment`, `PollingUnitResult`, `Flag`, `ReviewDecision`,
`ProvenanceEdge`. Postgres is canonical; Memgraph mirrors Party/Contract/Award/ownership edges.

---

## 8. Deployment & environments
- Local dev via docker-compose (Postgres, MinIO, Memgraph, search).
- Prod: self-hostable; components independently deployable. Election capture backend can scale
  independently for its episodic burst.
- Data mirrored to multiple hosts for resilience (P5).

---

## 9. Threat model (summary)
| Threat | Mitigation |
|--------|-----------|
| Source takedown / rot | WORM archive + mirrors (P1). |
| "You faked the data" | Merkle transparency log + open methodology + provenance. |
| Sybil / fake reports (election) | Observer accreditation + N-way corroboration + statistical sample. |
| Defamation / legal pressure | Evidence-linked claims, pre-pub legal review, nonpartisan framing. |
| DDoS / censorship | Static cacheable public layer + mirrored open data. |
| Data leak of contributors | PII minimization + encryption + access control. |
| Scraper blocking | Scrapling adaptivity + respectful cadence + FOI fallback. |

---

## 10. Phased roadmap → epics
Detailed epic/issue breakdown lives in `ROADMAP.md`. Summary:

- **E1 — Foundations**: repo, CI, dev env, docs, agent workflow, spec framework.
- **E2 — Source Registry**: schema, CRUD, health monitor, discovery agent (proposal-only).
- **E3 — Capture & Archive**: fetch layer + MinIO WORM + fetch records + hashing.
- **E4 — Extraction**: Magika router, Docling PDF tables, XLSX/JSON, Tesseract OCR fallback.
- **E5 — Normalize & Canonical store**: OCDS mapping, Postgres schema, provenance.
- **E6 — Entity Resolution & Graph**: matching, Memgraph projection, ownership enrichment.
- **E7 — Anomaly Engine**: red-flag rules + evidence outputs.
- **E8 — Intelligence/Agents**: agent roles + human-review queue.
- **E9 — API**: public read API + OpenAPI.
- **E10 — Frontend/Viz**: scrollytelling, dashboards, graph viz, 3D maps.
- **E11 — Election module**: EC8A capture, OCR, cross-checks, tamper-evident log.
- **E12 — Cross-cutting**: tamper-evidence log, observability, security, legal/FOI, partnerships.

---

## 11. Open questions (need human decision — flag with `needs-human`)
1. Graph engine — **Memgraph** (closed; docker-compose + `specs/0016`). AGE not needed for v1.
2. Orchestrator choice — **minimal Postgres `jobs` + worker + cron/Make** decided (#26 / `specs/0010`).
3. Repo/product name: keep **NaijaLedger**?
4. Hosting/infra budget & provider for prod?
5. Which state's procurement portal is the first end-to-end vertical slice?
6. Data-licensing for published datasets (e.g. ODbL / CC-BY)?
7. Legal entity strategy for Nigeria operations?
