# NaijaLedger web

React + Vite + TypeScript frontend.

## Setup

```bash
pnpm install
```

## Dev

```bash
pnpm dev
# Browser calls use VITE_API_BASE_URL (default /api → Vite proxy).
# Proxy target is VITE_ENGINE_URL (default http://localhost:8000); set in web/.env if the engine port differs.
```

## OpenAPI types

With the engine running:

```bash
make generate-api
```
