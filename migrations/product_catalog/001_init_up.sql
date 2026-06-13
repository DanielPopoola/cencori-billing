CREATE TABLE IF NOT EXISTS plans (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(100) NOT NULL,
    version           INTEGER NOT NULL DEFAULT 1,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    is_custom_pricing BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(name, version)
);

CREATE INDEX IF NOT EXISTS idx_plans_name_version ON plans(name, version);
CREATE INDEX IF NOT EXISTS idx_plans_active ON plans(is_active) WHERE is_active = true;


CREATE TABLE IF NOT EXISTS plan_pricing (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id      UUID NOT NULL REFERENCES plans(id),
    plan_version INTEGER NOT NULL,
    amount       BIGINT NOT NULL CHECK (amount >= 0),
    currency     VARCHAR(3) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(plan_id, plan_version, currency)
);

CREATE INDEX IF NOT EXISTS idx_plan_pricing_plan ON plan_pricing(plan_id, plan_version);

CREATE TABLE IF NOT EXISTS plan_entitlements (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id      UUID NOT NULL REFERENCES plans(id),
    plan_version INTEGER NOT NULL,
    feature_key  VARCHAR(100) NOT NULL,
    value        JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(plan_id, plan_version, feature_key)
);

CREATE INDEX IF NOT EXISTS idx_plan_entitlements_plan ON plan_entitlements(plan_id, plan_version);
CREATE INDEX IF NOT EXISTS idx_plan_entitlements_value ON plan_entitlements USING GIN(value);


CREATE TABLE IF NOT EXISTS product_catalog_outbox (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type        VARCHAR(100) NOT NULL,
    payload           JSONB NOT NULL,
    published         BOOLEAN NOT NULL DEFAULT false,
    published_at      TIMESTAMPTZ,
    publish_attempts  INTEGER NOT NULL DEFAULT 0,
    last_attempted_at TIMESTAMPTZ,
    error             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON product_catalog_outbox(created_at)
    WHERE published = false;