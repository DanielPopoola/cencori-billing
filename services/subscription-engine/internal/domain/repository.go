package domain

import "context"

type SubscriptionRepository interface {
	FindByID(ctx context.Context, id SubscriptionID) (*Subscription, error)
	FindByUserID(ctx context.Context, userID UserID) (*Subscription, error)
	SaveSubscription(ctx context.Context, sub *Subscription) error
	AppendEvent(ctx context.Context, subscriptionID SubscriptionID, eventType string, payload []byte) error
	EnqueueOutboxMessage(ctx context.Context, msg OutboxMessage) error
}
