# Local infrastructure (docker compose)

Services started by `docker compose up -d` from the repo root:

| Service | Port(s) | Purpose |
|---------|---------|---------|
| Postgres 16 + pgvector | 5432 | Canonical store and vector search |
| MinIO (Chainguard image) | 9000 (API), 9001 (console) | WORM raw archive |
| Memgraph | 7687 (Bolt), 7444 (HTTP) | Graph projection |

Credentials match `.env.example`. Data persists in named Docker volumes.

## MinIO image note

The upstream `minio/minio` repository was removed from Docker Hub (Quay pulls
are unauthorized). Local compose uses Chainguard's rebuild
(`cgr.dev/chainguard/minio`), pinned by digest in `docker-compose.yml`, with
`user: "0:0"` so the named volume is writable. The engine still talks S3 via
the MinIO Python client; only the container source changed.

## Postgres init

`docker/postgres/init.sql` enables the `vector` extension on first boot.
