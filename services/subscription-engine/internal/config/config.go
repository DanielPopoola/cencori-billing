package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

const (
	defaultPort                      = "8002"
	defaultDBPoolMaxConns            = 10
	defaultDBPoolMinConns            = 2
	defaultOutboxPollIntervalSeconds = 5
	defaultOutboxDeadLetterThreshold = 5
	defaultPaymentFailureThreshold   = 3
	defaultRetentionWindowDays       = 30
	defaultLogLevel                  = "info"
)

// Config is the single box of settings for this service.
type Config struct {
	// Infrastructure connections
	DatabaseURL           string
	KafkaBootstrapServers string

	Port string

	DBPoolMaxConns int32
	DBPoolMinConns int32

	OutboxPollIntervalSeconds int
	OutboxDeadLetterThreshold int

	// Business rules
	PaymentFailureSuspensionThreshold int
	RetentionWindowDays               int

	LogLevel string
}

// Load reads, parses, and validates all configuration in one pass.
func Load() (*Config, error) {
	var problems []string

	cfg := &Config{}

	cfg.DatabaseURL = requireString("DATABASE_URL", &problems)
	cfg.KafkaBootstrapServers = requireString("KAFKA_BOOTSTRAP_SERVERS", &problems)

	cfg.Port = getStringOrDefault("PORT", defaultPort)
	cfg.LogLevel = getStringOrDefault("LOG_LEVEL", defaultLogLevel)

	cfg.DBPoolMaxConns = int32(getIntOrDefault("DB_POOL_MAX_CONNS", defaultDBPoolMaxConns, &problems))
	cfg.DBPoolMinConns = int32(getIntOrDefault("DB_POOL_MIN_CONNS", defaultDBPoolMinConns, &problems))

	cfg.OutboxPollIntervalSeconds = getIntOrDefault(
		"OUTBOX_POLL_INTERVAL_SECONDS", defaultOutboxPollIntervalSeconds, &problems,
	)
	cfg.OutboxDeadLetterThreshold = getIntOrDefault(
		"OUTBOX_DEAD_LETTER_THRESHOLD", defaultOutboxDeadLetterThreshold, &problems,
	)

	cfg.PaymentFailureSuspensionThreshold = getIntOrDefault(
		"PAYMENT_FAILURE_SUSPENSION_THRESHOLD", defaultPaymentFailureThreshold, &problems,
	)
	cfg.RetentionWindowDays = getIntOrDefault(
		"RETENTION_WINDOW_DAYS", defaultRetentionWindowDays, &problems,
	)

	if cfg.DBPoolMinConns > cfg.DBPoolMaxConns {
		problems = append(problems, "DB_POOL_MIN_CONNS cannot exceed DB_POOL_MAX_CONNS")
	}

	if len(problems) > 0 {
		return nil, fmt.Errorf("invalid configuration:\n  - %s", strings.Join(problems, "\n  - "))
	}

	return cfg, nil
}

func requireString(key string, problems *[]string) string {
	val := os.Getenv(key)
	if val == "" {
		*problems = append(*problems, fmt.Sprintf("%s is required but not set", key))
	}
	return val
}

func getStringOrDefault(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

func getIntOrDefault(key string, fallback int, problems *[]string) int {
	raw := os.Getenv(key)
	if raw == "" {
		return fallback
	}
	val, err := strconv.Atoi(raw)
	if err != nil {
		*problems = append(*problems, fmt.Sprintf("%s must be an integer, got %q", key, raw))
		return fallback
	}
	return val
}
