package domain

import "errors"

var (
	ErrSubscriptionNotFound      = errors.New("subscription not found")
	ErrInvalidStateTransition    = errors.New("invalid state transition")
	ErrSubscriptionAlreadyExists = errors.New("subscription already exists")
)
