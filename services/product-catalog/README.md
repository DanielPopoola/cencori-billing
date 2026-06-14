# Product Catalog

The Product Catalog is the foundation of the Cencori billing system. It is
the single source of truth for what Cencori sells — plans, prices, feature
entitlements, and their full version history.

Every other billing component depends on this service. Nothing else is built
until this is stable.

---

## What it does

- **Plans** — named tiers (Free, Pro, Team, Enterprise) with immutable version history
- **Pricing** — monthly amount per plan version per currency, annual amount derived on the fly
- **Entitlements** — feature keys and limits each plan version grants

## What it does not do

- Manage subscription state — that is the Subscription Engine
- Charge customers — that is the Payment Service
- Enforce feature access at request time — that is the Entitlement Service

---

## Quick start

```bash
# From repo root
cp .env.example .env
make up           # start postgres, redis, kafka
make migrate-pc   # run migrations
make seed-pc      # seed Free, Pro, Team, Enterprise plans
make dev-pc       # start service on :8001
```

Swagger UI: http://localhost:8001/docs

---

## Architecture

```
FastAPI HTTP API
      │
      ├── Redis (primary read path, ~30ms)
      │       └── cache miss → PostgreSQL → repopulate
      │
      └── PostgreSQL (write path + fallback)
              │
              └── product_catalog_outbox
                        │
                        └── Outbox Worker → Kafka
                                  ├── plan.version.created
                                  └── plan.version.deactivated
```

---

## Data model

```
plan_families          plans                plan_pricing
─────────────          ──────               ────────────
id (PK)          ◄──── family_id (FK)       plan_id (FK) ──► plan_families.id
name                   id (PK)              plan_version
is_custom_pricing      version              amount (minor units)
                       is_active            currency (ISO 4217)

plan_entitlements
─────────────────
plan_id (FK) ──► plan_families.id
plan_version
feature_key
value (JSONB)    {"type": "boolean", "enabled": true}
                 {"type": "numeric", "limit": 50000}
```

`plan_families` owns the stable plan identity. `plans` owns version rows.
Pricing and entitlements reference the family, filtered by version at query time.

---

## Key design decisions

**Plans are immutable.** Changing any attribute creates a new version. The
previous version is frozen forever. Subscribers stay on their version until
renewal.

**Annual price is derived, never stored.** `monthly × 12 × (1 - ANNUAL_DISCOUNT_RATE)`.
The rate is an environment variable. The derived amount is snapshotted on the
subscription record at checkout and never recalculated retroactively.

**Redis is the primary read path.** Plan data changes rarely but is read
constantly. Cache failures are non-fatal — the service degrades to PostgreSQL
reads, not an outage.

**Enterprise has no pricing row.** `is_custom_pricing = true` on the family.
The pricing endpoint returns a typed response (200, never 404) so consumers
stay consistent without special-casing Enterprise.

**Transactional outbox.** Plan writes and Kafka events are written in the
same database transaction. A background worker publishes unpublished rows.
Events are never lost — at-least-once delivery, consumers deduplicate via
`event_id`.

---

## API

Base URL: `/api/v1`

Write endpoints require `X-Admin-Token` header.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/plans` | Create a new plan at version 1 |
| `POST` | `/plans/:id/versions` | Create a new version of an existing plan |
| `PATCH` | `/plans/:id/versions/:version/deactivate` | Deactivate a plan version |
| `GET` | `/plans` | List all active plans |
| `GET` | `/plans/:id/versions/latest` | Get the current active version |
| `GET` | `/plans/:id/versions/:version` | Get a specific version |
| `GET` | `/plans/:id/versions/:version/pricing?currency=NGN` | Get pricing with derived annual amount |
| `GET` | `/plans/:id/versions/:version/entitlements` | Get all entitlements |
| `GET` | `/plans/:id/versions/:version/entitlements/:key` | Get a single entitlement |

All responses use a standard envelope:

```json
{"success": true, "message": "OK", "data": {...}}
{"success": false, "message": "...", "error": {"code": "plan_not_found", "details": null}}
```

---

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | required |
| `REDIS_URL` | Redis connection string | required |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | required |
| `ADMIN_TOKEN` | Static token for write endpoints | required |
| `ANNUAL_DISCOUNT_RATE` | Annual billing discount (0.0–1.0) | `0.17` |
| `DB_POOL_SIZE` | SQLAlchemy pool size | `5` |
| `DB_MAX_OVERFLOW` | Pool max overflow | `10` |
| `DB_POOL_TIMEOUT` | Pool connection timeout (seconds) | `30` |
| `OUTBOX_POLL_INTERVAL_SECONDS` | Outbox worker poll frequency | `5` |
| `OUTBOX_DEAD_LETTER_THRESHOLD` | Max publish attempts before skip | `10` |
| `CACHE_TTL_SECONDS` | Redis TTL for plan data | `3600` |

---

## Kafka events

| Topic | Trigger |
|-------|---------|
| `plan.version.created` | New plan or new plan version created |
| `plan.version.deactivated` | Version explicitly deactivated or superseded |

All events use a standard envelope with `event_id`, `event_type`, `timestamp`,
and `payload`. Consumers must handle duplicates idempotently via `event_id`.

---

## Running tests

```bash
cd services/product-catalog
uv run pytest
```

Requires Docker — testcontainers spins up a real PostgreSQL instance.
Each test runs in a transaction that rolls back after — no manual cleanup needed.

---

## Project structure

```
services/product-catalog/
├── app/
│   ├── core/           # config, database, cache, logging, response, exceptions
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response schemas
│   ├── repositories/   # SQL queries (db/) and cache helpers (cache/)
│   ├── services/       # business logic, transaction ownership
│   ├── routers/        # HTTP endpoints, pure wiring
│   └── workers/        # outbox worker
├── migrations/         # Alembic migrations (in repo root migrations/product_catalog/)
├── seed/               # seed.py — baseline Free, Pro, Team, Enterprise plans
└── tests/
    ├── test_plan_api.py      # route layer tests
    └── test_plan_service.py  # service layer tests
```
