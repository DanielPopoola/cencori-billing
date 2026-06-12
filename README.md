# Cencori Billing System

A billing system for the Cencori AI infrastructure platform. Built as a learning project to understand billing system patterns: plan versioning, idempotency, event-driven state machines, and outbox publishing.

## Services

| Service | Language | Port | Status |
|---------|----------|------|--------|
| product-catalog | Python 3.12 | 8001 | In progress |
| subscription-engine | Go | 8002 | Planned |
| payment-service | Go | 8003 | Planned |

## Quick Start

```bash
cp .env.example .env
make up          # start postgres, redis, kafka
make migrate-pc  # run product_catalog migrations
make seed-pc     # seed Free, Pro, Team, Enterprise plans
make dev-pc      # start product-catalog on :8001
```

## Repository Layout

```
cencori/
├── docker-compose.yml       # all infrastructure
├── Makefile                 # top-level convenience commands
├── migrations/              # SQL migrations, per service, run in order
│   └── product_catalog/
├── shared/
│   └── events/              # Kafka event schemas (JSON)
└── services/
    └── product-catalog/     # FastAPI service
```

## Architecture

See `services/product-catalog/` for the Product Catalog TDD and system spec.
Each service owns its own tables. No service reads another service's tables.
All inter-service communication goes through Kafka.
