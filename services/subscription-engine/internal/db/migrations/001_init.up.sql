CREATE TABLE IF NOT EXISTS subscriptions (
    id                        UUID PRIMARY KEY,
    user_id                   UUID NOT NULL,
    family_id                 UUID NOT NULL,
    plan_version              INTEGER NOT NULL,
    state                     subscription_state NOT NULL,
    billing_cycle_policy      billing_cycle_policy NOT NULL,
    anchor_date               TIMESTAMPTZ NOT NULL, 
    billing_interval          VARCHAR NOT NULL DEFAULT 'monthly',
    payment_failure_count     INTEGER NOT NULL DEFAULT 0,
    contract_ends_at          TIMESTAMPTZ,
    cancellation_reason       cancellation_reason,
    cancelled_at              TIMESTAMPTZ,
    data_retention_expires_at TIMESTAMPTZ,
    data_purged_at            TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),


    UNIQUE(user_id) WHERE state != 'cancelled'
);

CREATE INDEX IF NOT EXISTS ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_state ON subscriptions(state);


CREATE INDEX IF NOT EXISTS idx_subscriptions_state_anchor
    ON subscriptions(state, anchor_date)
    WHERE state IN ('cancel_at_period_end', 'past_due', 'suspended');


CREATE TABLE IF NOT EXISTS plan_entitlement_cache (
    family_id    UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    feature_key  VARCHAR NOT NULL,
    value        JSONB NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (family_id, plan_version, feature_key)
);

CREATE TABLE IF NOT EXISTS subscription_events (
    id              UUID PRIMARY KEY,
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),
    event_type      VARCHAR NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscription_events_subscription_id 
    ON subscription_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_events_created_at 
    ON subscription_events(subscription_id, created_at DESC);


CREATE TABLE IF NOT EXISTS outbox (
    id                UUID PRIMARY KEY,
    aggregate_id      UUID NOT NULL,
    aggregate_type    VARCHAR NOT NULL DEFAULT 'subscription',
    event_type        VARCHAR NOT NULL,
    payload           JSONB NOT NULL,
    published         BOOLEAN NOT NULL DEFAULT false,
    published_at      TIMESTAMPTZ,
    publish_attempts  INTEGER NOT NULL DEFAULT 0,
    last_attempted_at TIMESTAMPTZ,
    error             VARCHAR,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON outbox(created_at) WHERE published = false;

CREATE TABLE IF NOT EXISTS scheduled_changes (
    id              UUID PRIMARY KEY,
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),
    change_type     VARCHAR NOT NULL,        -- 'downgrade' | 'cancellation'
    payload         JSONB NOT NULL,          -- e.g. { "family_id": "uuid", "plan_version": 1 }
    effective_at    TIMESTAMPTZ NOT NULL,
    applied_at      TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_changes_due
    ON scheduled_changes(effective_at)
    WHERE applied_at IS NULL AND cancelled_at IS NULL;


CREATE TABLE IF NOT EXISTS idempotency_keys (
    id              UUID PRIMARY KEY,
    key             VARCHAR(255) NOT NULL UNIQUE,
    response_status INTEGER NOT NULL,
    response_body   JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idempotency_keys_key ON idempotency_keys(key);
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_expires_at ON idempotency_keys(expires_at);