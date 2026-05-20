.PHONY: seed generate-data build test lint typecheck dev dev-api dev-web dev-compose dev-up dev-down dev-logs dev-ps dev-smoke

dev-api:
	uv sync --package api
	uv run uvicorn apps.api.main:app --reload --port 8000

dev-web:
	cd apps/web && npm run dev

dev:
	@echo "Starting API on :8000 and Web on :3000 ..."
	@$(MAKE) dev-api & $(MAKE) dev-web

dev-compose:
	docker compose --env-file .env -f infra/compose/compose.yaml up --build

dev-up:
	docker compose --env-file .env -f infra/compose/compose.yaml up -d --build

dev-down:
	docker compose --env-file .env -f infra/compose/compose.yaml down

dev-logs:
	docker compose --env-file .env -f infra/compose/compose.yaml logs --tail=100

dev-ps:
	docker compose --env-file .env -f infra/compose/compose.yaml ps

dev-smoke:
	curl -sf http://localhost:$${API_PORT:-8000}/healthz

generate-data:
	uv run python scripts/generate_sample_data.py

seed: generate-data
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
