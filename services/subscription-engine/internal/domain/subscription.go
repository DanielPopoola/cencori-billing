package domain

import "time"

type State string

const (
	StateActive            State = "active"
	StatePastDue           State = "past_due"
	StateSuspended         State = "suspended"
	StateCancelAtPeriodEnd State = "cancel_at_period_end"
	StateCancelled         State = "cancelled"
)

type CancellationReason string

const (
	CancellationVoluntary        CancellationReason = "voluntary"
	CancellationPaymentExhausted CancellationReason = "payment_exhausted"
)

type BillingCyclePolicy string

const (
	BillingCycleRollingWindow BillingCyclePolicy = "rolling_window"
	BillingCycleCalendarMonth BillingCyclePolicy = "calendar_month"
	BillingCycleContractBased BillingCyclePolicy = "contract_based"
)

type Subscription struct {
	ID                  SubscriptionID
	UserID              UserID
	FamilyID            FamilyID
	PlanVersion         int
	State               State
	BillingCyclePolicy  BillingCyclePolicy
	AnchorDate          time.Time
	BillingInterval     string
	PaymentFailureCount int
	CancellationReason  *CancellationReason
	CancelledAt         *time.Time

	pendingEvents []Event
}

// PullEvents returns and clears events accumulated since the last call.
func (s *Subscription) PullEvents() []Event {
	events := s.pendingEvents
	s.pendingEvents = nil
	return events
}

func (s *Subscription) raise(e Event) {
	s.pendingEvents = append(s.pendingEvents, e)
}

// NewSubscription creates a subscription on the given plan, starting in
// the active state. Used for both free-plan signup and any other initial
// subscription creation — Phase 1 has no separate "trial" state.
func NewSubscription(
	userID UserID,
	familyID FamilyID,
	planVersion int,
	billingCyclePolicy BillingCyclePolicy,
	billingInterval string,
	now time.Time,
) *Subscription {
	s := &Subscription{
		ID:                  NewSubscriptionID(),
		UserID:              userID,
		FamilyID:            familyID,
		PlanVersion:         planVersion,
		State:               StateActive,
		BillingCyclePolicy:  billingCyclePolicy,
		AnchorDate:          now,
		BillingInterval:     billingInterval,
		PaymentFailureCount: 0,
	}

	s.raise(SubscriptionCreated{
		BaseEvent:   newBaseEvent(s.ID, now),
		UserID:      userID,
		FamilyID:    familyID,
		PlanVersion: planVersion,
	})

	return s
}

// MarkPastDue records a failed payment.
func (s *Subscription) MarkPastDue(now time.Time, suspensionThreshold int) error {
	if s.State != StateActive && s.State != StatePastDue {
		return ErrInvalidStateTransition
	}

	s.PaymentFailureCount++
	s.State = StatePastDue

	s.raise(SubscriptionMarkedPastDue{
		BaseEvent:           newBaseEvent(s.ID, now),
		PaymentFailureCount: s.PaymentFailureCount,
	})

	if s.PaymentFailureCount >= suspensionThreshold {
		s.State = StateSuspended
		s.raise(SubscriptionSuspended{
			BaseEvent:           newBaseEvent(s.ID, now),
			PaymentFailureCount: s.PaymentFailureCount,
		})
	}

	return nil
}

// RecoverPayment handles payment.succeeded — resets the failure count and
// returns to active from either past_due or suspended.
func (s *Subscription) RecoverPayment(now time.Time) error {
	if s.State != StatePastDue && s.State != StateSuspended {
		return ErrInvalidStateTransition
	}

	s.PaymentFailureCount = 0
	s.State = StateActive

	s.raise(SubscriptionReactivated{
		BaseEvent: newBaseEvent(s.ID, now),
	})

	return nil
}

// Cancel schedules a voluntary cancellation for period end.
func (s *Subscription) Cancel(now time.Time, effectiveAt time.Time) error {
	if s.State != StateActive {
		return ErrInvalidStateTransition
	}

	s.State = StateCancelAtPeriodEnd

	s.raise(SubscriptionCancellationScheduled{
		BaseEvent:   newBaseEvent(s.ID, now),
		EffectiveAt: effectiveAt,
	})

	return nil
}

// FinaliseCancellation applies a scheduled cancellation once its period has actually ended.
func (s *Subscription) FinaliseCancellation(now time.Time, reason CancellationReason, retentionExpiresAt time.Time) error {
	if s.State != StateCancelAtPeriodEnd && s.State != StateSuspended {
		return ErrInvalidStateTransition
	}

	s.State = StateCancelled
	s.CancellationReason = &reason
	s.CancelledAt = &now

	s.raise(SubscriptionCancelled{
		BaseEvent: newBaseEvent(s.ID, now),
		Reason:    reason,
	})

	_ = retentionExpiresAt // stored by the repository, not the aggregate

	return nil
}

// Reactivate resubscribes a cancelled subscription within its retention window.
func (s *Subscription) Reactivate(now time.Time) error {
	if s.State != StateCancelled {
		return ErrInvalidStateTransition
	}

	s.State = StateActive
	s.CancellationReason = nil
	s.CancelledAt = nil
	s.PaymentFailureCount = 0

	s.raise(SubscriptionReactivated{
		BaseEvent: newBaseEvent(s.ID, now),
	})

	return nil
}
