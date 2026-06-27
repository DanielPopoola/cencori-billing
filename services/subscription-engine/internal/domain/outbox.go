package domain

type OutboxMessage struct {
	AggregateID   SubscriptionID
	AggregateType string // always "subscription" for this service
	EventType     string // from Event.EventType()
	Payload       []byte // JSON-encoded Event
}
