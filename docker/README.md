# Local infrastructure (docker compose)

Services started by `docker compose up -d` from the repo root:

| Service | Port(s) | Purpose |
|---------|---------|---------|
| Postgres 16 + pgvector | 5432 | Canonical store and vector search |
| MinIO | 9000 (API), 9001 (console) | WORM raw archive |
| Memgraph | 7687 (Bolt), 7444 (HTTP) | Graph projection |

Credentials match `.env.example`. Data persists in named Docker volumes.

## Postgres init

`docker/postgres/init.sql` enables the `vector` extension on first boot.
