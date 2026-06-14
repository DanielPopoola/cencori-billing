.PHONY: up down logs migrate-pc seed-pc dev-pc

# ── Infrastructure ────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# ── Product Catalog ───────────────────────────────────────
migrate-pc:
	@echo "Running product_catalog migrations..."
	cd services/product-catalog && uv run alembic upgrade head
seed-pc:
	cd services/product-catalog && uv run python -m app.seed.seed
dev-pc:
	cd services/product-catalog && uv run uvicorn app.main:app --reload --port 8001
