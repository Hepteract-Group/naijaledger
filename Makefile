.PHONY: install install-engine install-web lint typecheck test format dev-engine dev-web generate-api docker-up docker-down docker-ps docker-config migrate seed-sources health-monitor

DATABASE_URL ?= postgresql+psycopg://naijaledger:naijaledger@localhost:5432/naijaledger
export DATABASE_URL

install: install-engine install-web

install-engine:
	cd engine && uv sync --all-extras

install-web:
	pnpm install

lint: lint-engine lint-web

lint-engine:
	cd engine && uv run ruff check src tests
	cd engine && uv run ruff format --check src tests

lint-web:
	pnpm lint

typecheck: typecheck-engine typecheck-web

typecheck-engine:
	cd engine && uv run mypy src

typecheck-web:
	pnpm typecheck

test: test-engine test-web

test-engine:
	cd engine && uv run pytest

test-web:
	pnpm --filter @naijaledger/web test

format: format-engine format-web

format-engine:
	cd engine && uv run ruff format src tests

format-web:
	pnpm format

dev-engine:
	cd engine && uv run naijaledger-api

dev-web:
	pnpm dev:web

# Requires engine running on localhost:8000
generate-api:
	pnpm --filter @naijaledger/web generate-api

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-ps:
	docker compose ps

docker-config:
	docker compose config

migrate:
	cd engine && uv run alembic upgrade head

seed-sources: migrate
	cd engine && uv run naijaledger-seed

health-monitor:
	cd engine && uv run naijaledger-health-monitor
