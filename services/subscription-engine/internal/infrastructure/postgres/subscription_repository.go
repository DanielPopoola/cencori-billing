package postgres

import (
	"context"
	"errors"

	"github.com/DanielPopoola/cencori-billing/services/subscription-engine/internal/db"
	"github.com/DanielPopoola/cencori-billing/services/subscription-engine/internal/domain"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

type subscriptionRepository struct {
	exec db.Executor
}

// NewSubscriptionRepository creates a SubscriptionRepository. exec can be
// either db.DB's pool (outside a transaction) or a pgx.Tx (inside one via
// db.WithTransaction) — the repository doesn't know or care which.
func NewSubscriptionRepository(exec db.Executor) domain.SubscriptionRepository {
	return &subscriptionRepository{exec: exec}
}

func (r *subscriptionRepository) FindByID(ctx context.Context, id domain.SubscriptionID) (*domain.Subscription, error) {
	row, err := r.queryOne(ctx, "WHERE id = $1", uuid.UUID(id))
	if err != nil {
		return nil, err
	}
	return row, nil
}

func (r *subscriptionRepository) FindByUserID(ctx context.Context, userID domain.UserID) (*domain.Subscription, error) {
	row, err := r.queryOne(ctx, "WHERE user_id = $1 AND state != 'cancelled'", uuid.UUID(userID))
	if err != nil {
		return nil, err
	}
	return row, nil
}

func (r *subscriptionRepository) SaveSubscription(ctx context.Context, sub *domain.Subscription) error {
	row := subscriptionToRow(sub)

	sql := `
		INSERT INTO subscriptions (
			id, user_id, family_id, plan_version, state, billing_cycle_policy,
			anchor_date, billing_interval, payment_failure_count,
			cancellation_reason, cancelled_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		ON CONFLICT (id) DO UPDATE SET
			family_id             = EXCLUDED.family_id,
			plan_version          = EXCLUDED.plan_version,
			state                 = EXCLUDED.state,
			billing_cycle_policy  = EXCLUDED.billing_cycle_policy,
			billing_interval      = EXCLUDED.billing_interval,
			payment_failure_count = EXCLUDED.payment_failure_count,
			cancellation_reason   = EXCLUDED.cancellation_reason,
			cancelled_at          = EXCLUDED.cancelled_at,
			updated_at            = now()
	`

	_, err := r.exec.Exec(ctx, sql,
		row.ID, row.UserID, row.FamilyID, row.PlanVersion, row.State,
		row.BillingCyclePolicy, row.AnchorDate, row.BillingInterval,
		row.PaymentFailureCount, row.CancellationReason, row.CancelledAt,
	)
	return err
}

func (r *subscriptionRepository) AppendEvent(ctx context.Context, subscriptionID domain.SubscriptionID, eventType string, payload []byte) error {
	sql := `
		INSERT INTO subscription_events (id, subscription_id, event_type, payload)
		VALUES (gen_random_uuid(), $1, $2, $3)
	`
	_, err := r.exec.Exec(ctx, sql, uuid.UUID(subscriptionID), eventType, payload)
	return err
}

func (r *subscriptionRepository) EnqueueOutboxMessage(ctx context.Context, msg domain.OutboxMessage) error {
	sql := `
		INSERT INTO outbox (id, aggregate_id, aggregate_type, event_type, payload)
		VALUES (gen_random_uuid(), $1, $2, $3, $4)
	`
	_, err := r.exec.Exec(ctx, sql,
		uuid.UUID(msg.AggregateID), msg.AggregateType, msg.EventType, msg.Payload,
	)
	return err
}

func (r *subscriptionRepository) queryOne(ctx context.Context, whereClause string, arg any) (*domain.Subscription, error) {
	sql := `
		SELECT id, user_id, family_id, plan_version, state, billing_cycle_policy,
		       anchor_date, billing_interval, payment_failure_count,
		       cancellation_reason, cancelled_at
		FROM subscriptions
		` + whereClause

	var row subscriptionRow
	err := r.exec.QueryRow(ctx, sql, arg).Scan(
		&row.ID, &row.UserID, &row.FamilyID, &row.PlanVersion, &row.State,
		&row.BillingCyclePolicy, &row.AnchorDate, &row.BillingInterval,
		&row.PaymentFailureCount, &row.CancellationReason, &row.CancelledAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domain.ErrSubscriptionNotFound
		}
		return nil, err
	}

	return rowToSubscription(row), nil
}
