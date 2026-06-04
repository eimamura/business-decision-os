.PHONY: migrate seed generate-data codegen build test lint typecheck dev dev-api dev-web dev-up dev-down dev-logs dev-ps dev-smoke

WEB_PORT ?= 3002
API_PORT ?= 8002

COMPOSE = WEB_PORT=$(WEB_PORT) API_PORT=$(API_PORT) docker compose --env-file .env -f infra/compose/compose.yaml

dev-api:
	uv sync --package api
	uv run uvicorn apps.api.main:app --reload --port $(API_PORT)

dev-web:
	cd apps/web && npm run dev -- --port $(WEB_PORT)

dev:
	@echo "Starting API on :$(API_PORT) and Web on :$(WEB_PORT) ..."
	@$(MAKE) dev-api & $(MAKE) dev-web

dev-up:
	$(COMPOSE) up --build

dev-down:
	$(COMPOSE) down

dev-logs:
	$(COMPOSE) logs --tail=100 --follow

dev-ps:
	$(COMPOSE) ps

dev-smoke:
	curl -sf http://localhost:$(API_PORT)/healthz

migrate:
	cd apps/api && uv run alembic upgrade head

generate-data:
	uv run python scripts/generate_sample_data.py

seed: migrate generate-data
	uv run python scripts/seed_db.py

build:
	cd apps/api && uv sync
	cd apps/web && npm install
	@echo "Build OK"

test:
	uv run pytest tests/ -x -q

lint:
	uv run ruff check packages/ apps/api/ scripts/

typecheck:
	uv run mypy packages/ apps/api/

codegen:
	uv run python scripts/generate_schemas.py
	@echo "Verifying no TS compile errors after codegen..."
	cd apps/web && npx tsc --noEmit
	@echo "codegen OK"
