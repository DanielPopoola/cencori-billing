package postgres

import (
	"time"

	"github.com/DanielPopoola/cencori-billing/services/subscription-engine/internal/domain"
	"github.com/google/uuid"
)

// subscriptionRow mirrors the subscriptions table exactly, including
// Postgres NULLs as pointers. Scanning into this first, then converting,
// keeps pgx's row.Scan() calls boring and keeps the nullable-field
// handling in one place instead of scattered across every query method.
type subscriptionRow struct {
	ID                  uuid.UUID
	UserID              uuid.UUID
	FamilyID            uuid.UUID
	PlanVersion         int
	State               string
	BillingCyclePolicy  string
	AnchorDate          time.Time
	BillingInterval     string
	PaymentFailureCount int
	CancellationReason  *string
	CancelledAt         *time.Time
}

func rowToSubscription(r subscriptionRow) *domain.Subscription {
	sub := &domain.Subscription{
		ID:                  domain.SubscriptionID(r.ID),
		UserID:              domain.UserID(r.UserID),
		FamilyID:            domain.FamilyID(r.FamilyID),
		PlanVersion:         r.PlanVersion,
		State:               domain.State(r.State),
		BillingCyclePolicy:  domain.BillingCyclePolicy(r.BillingCyclePolicy),
		AnchorDate:          r.AnchorDate,
		BillingInterval:     r.BillingInterval,
		PaymentFailureCount: r.PaymentFailureCount,
		CancelledAt:         r.CancelledAt,
	}

	if r.CancellationReason != nil {
		reason := domain.CancellationReason(*r.CancellationReason)
		sub.CancellationReason = &reason
	}

	return sub
}

func subscriptionToRow(sub *domain.Subscription) subscriptionRow {
	row := subscriptionRow{
		ID:                  uuid.UUID(sub.ID),
		UserID:              uuid.UUID(sub.UserID),
		FamilyID:            uuid.UUID(sub.FamilyID),
		PlanVersion:         sub.PlanVersion,
		State:               string(sub.State),
		BillingCyclePolicy:  string(sub.BillingCyclePolicy),
		AnchorDate:          sub.AnchorDate,
		BillingInterval:     sub.BillingInterval,
		PaymentFailureCount: sub.PaymentFailureCount,
		CancelledAt:         sub.CancelledAt,
	}

	if sub.CancellationReason != nil {
		reason := string(*sub.CancellationReason)
		row.CancellationReason = &reason
	}

	return row
}
