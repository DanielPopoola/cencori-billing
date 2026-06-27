package domain

import (
	"time"

	"github.com/google/uuid"
)

// Event is implemented by every domain event this aggregate produces.
type Event interface {
	EventType() string
}

// BaseEvent carries the fields every event needs: an ID for consumer-side
// dedup, when it happened, and which subscription it concerns. Embedded
// (not named) in each concrete event so e.g. SubscriptionUpgraded.EventID
// works directly.
type BaseEvent struct {
	EventID        uuid.UUID
	SubscriptionID SubscriptionID
	OccurredAt     time.Time
}

func newBaseEvent(subID SubscriptionID, occurredAt time.Time) BaseEvent {
	return BaseEvent{
		EventID:        uuid.New(),
		SubscriptionID: subID,
		OccurredAt:     occurredAt,
	}
}

type SubscriptionCreated struct {
	BaseEvent
	UserID      UserID
	FamilyID    FamilyID
	PlanVersion int
}

func (e SubscriptionCreated) EventType() string { return "subscription.created" }

type SubscriptionMarkedPastDue struct {
	BaseEvent
	PaymentFailureCount int
}

func (e SubscriptionMarkedPastDue) EventType() string { return "subscription.marked.past_due" }

type SubscriptionSuspended struct {
	BaseEvent
	PaymentFailureCount int
}

func (e SubscriptionSuspended) EventType() string { return "subscription.suspended" }

type SubscriptionCancellationScheduled struct {
	BaseEvent
	EffectiveAt time.Time
}

func (e SubscriptionCancellationScheduled) EventType() string {
	return "subscription.cancellation.scheduled"
}

type SubscriptionCancelled struct {
	BaseEvent
	Reason CancellationReason
}

func (e SubscriptionCancelled) EventType() string { return "subscription.cancelled" }

// SubscriptionReactivated covers both reactivation transitions in TDD §6:
// suspended -> active and cancelled -> active. §7 lists a single topic
// for both cases.
type SubscriptionReactivated struct {
	BaseEvent
}

func (e SubscriptionReactivated) EventType() string { return "subscription.reactivated" }
