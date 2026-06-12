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
	@for f in migrations/product_catalog/*.sql; do \
		echo "  $$f"; \
		docker exec -i $$(docker compose ps -q postgres) \
			psql -U cencori -d cencori < "$$f"; \
	done

seed-pc:
	docker exec -i $$(docker compose ps -q postgres) \
		psql -U cencori -d cencori < services/product-catalog/seed/seed.sql

dev-pc:
	cd services/product-catalog && uv run uvicorn app.main:app --reload --port 8001
