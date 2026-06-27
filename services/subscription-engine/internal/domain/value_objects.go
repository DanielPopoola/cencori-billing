package domain

import (
	"time"

	"github.com/google/uuid"
)

// SubscriptionID identifies a subscription.
type SubscriptionID uuid.UUID

// UserID identifies the account owner.
type UserID uuid.UUID

// FamilyID is a soft reference to product_catalog.plan_families.id.
type FamilyID uuid.UUID

func NewSubscriptionID() SubscriptionID {
	return SubscriptionID(uuid.New())
}

func (id SubscriptionID) String() string {
	return uuid.UUID(id).String()
}

func (id UserID) String() string {
	return uuid.UUID(id).String()
}

func (id FamilyID) String() string {
	return uuid.UUID(id).String()
}

// Money is an amount in minor units (kobo, cents) plus an ISO 4217 code.
type Money struct {
	Amount   int64
	Currency string
}

// BillingPeriod is a cycle's boundaries, derived from anchor_date + policy.
type BillingPeriod struct {
	StartedAt time.Time
	EndsAt    time.Time
}
