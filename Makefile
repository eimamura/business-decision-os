.PHONY: seed generate-data build test lint typecheck

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
