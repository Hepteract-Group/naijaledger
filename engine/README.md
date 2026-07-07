# NaijaLedger engine

Python package: ingestion, normalization, entity resolution, and read API.

## Setup

```bash
cd engine
uv sync --all-extras
```

## Run API (health check)

```bash
uv run naijaledger-api
# GET http://localhost:8000/health
# OpenAPI: http://localhost:8000/openapi.json
```

## Migrations

```bash
export DATABASE_URL=postgresql+psycopg://naijaledger:naijaledger@localhost:5432/naijaledger
uv run alembic upgrade head
```
