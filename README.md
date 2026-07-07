# NaijaLedger

**An open civic-accountability data platform for Nigeria.**

NaijaLedger makes public information *undeniable, durable, and legible*. It ingests public data,
preserves it, connects the dots, surfaces anomalies with evidence, and tells the story visually —
with every published claim traceable to a source document.

Two product surfaces share one engine:

1. **Public-finance transparency** — budgets, procurement/contracting, and payments: captured,
   normalized (OCDS), entity-resolved, graphed, and checked for red flags.
2. **Election-results verification** — polling-unit result sheets captured at source, cross-checked
   against official portals, and preserved in a tamper-evident record.

## Principles

- **Preservation-first.** Government transparency sources rot; we archive them the moment we can
  reach them (write-once + content hash).
- **Provenance everywhere.** Every datum links to its source document, page, and fetch record.
- **Human-in-the-loop for publication.** AI proposes; a human verifies before anything is published
  as fact. We do not publish unverified accusations.
- **Open & nonpartisan.** Open code and methodology; lawful data acquisition; not affiliated with
  any party or candidate. Openness is our security model.

## Status

Early. The **design is the source of truth** and lives in
[`docs/architecture/`](docs/architecture/SYSTEM_DESIGN.md). The system is built incrementally by AI
agents following the loop and spec-driven workflow in [`AGENTS.md`](AGENTS.md).

## Repository layout

```
/engine   Python 3.11+ (uv, FastAPI, Alembic, ruff, mypy)
/web      TypeScript + React (Vite, pnpm, eslint, prettier)
/specs    Spec-driven development contracts
/docs     Architecture and design
```

## Local development

Prerequisites: [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/), Make.

```bash
make install          # uv sync + pnpm install
make docker-up        # Postgres, MinIO, Memgraph (see docker-compose.yml)
make dev-engine       # API on http://localhost:8000/health
make dev-web          # UI on http://localhost:5173 (or next free port)
make lint typecheck test
```

Copy `.env.example` to `.env` for local overrides. OpenAPI → TS types: `make generate-api` (engine must be running).

- [System design](docs/architecture/SYSTEM_DESIGN.md)
- [Data model](docs/architecture/data-model.md)
- [Roadmap (epics → issues)](docs/architecture/ROADMAP.md)
- [Specs](specs/)

## Tech (planned)

Python engine (ingestion, extraction, entity resolution, agents) · PostgreSQL (canonical) · MinIO
(WORM archive) · Memgraph (graph) · FastAPI · TypeScript + React/Vite web · MapLibre + deck.gl.

## License

See [LICENSE](LICENSE).

---

> NaijaLedger is a transparency and accountability project. It operates lawfully and nonpartisanly, and
> is not a tool for evasion, anonymity, or targeting individuals.
