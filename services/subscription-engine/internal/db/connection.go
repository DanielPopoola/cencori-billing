package db

import (
	"context"
	"errors"
	"fmt"

	"github.com/DanielPopoola/cencori-billing/services/subscription-engine/internal/config"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// DB wraps the connection pool
type DB struct {
	pool *pgxpool.Pool
}

// Executor defines the interface for executing database queries
type Executor interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// Connect establishes a connection to the database
func Connect(ctx context.Context, cfg *config.Config) (*DB, error) {
	poolCfg, err := pgxpool.ParseConfig(cfg.DatabaseURL)
	if err != nil {
		return nil, fmt.Errorf("parsing database url: %w", err)
	}

	poolCfg.MaxConns = cfg.DBPoolMaxConns
	poolCfg.MinConns = cfg.DBPoolMinConns

	pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		return nil, fmt.Errorf("creating connection pool: %w", err)
	}

	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("pinging database: %w", err)
	}

	return &DB{pool: pool}, nil
}

// Close releases all pool connections.
func (db *DB) Close() {
	db.pool.Close()
}

// Pool exposes the underlying pool as an Executor
func (db *DB) Pool() Executor {
	return db.pool
}

// WithTransaction runs fn inside a single database transaction. fn
// receives an Executor backed by the transaction (a pgx.Tx)
// Commits on success, rolls back on any returned error or panic.
func (db *DB) WithTransaction(ctx context.Context, fn func(ctx context.Context, exec Executor) error) error {
	tx, err := db.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("beginning transaction: %w", err)
	}

	defer func() {
		if p := recover(); p != nil {
			_ = tx.Rollback(ctx)
			panic(p)
		}
	}()

	if err := fn(ctx, tx); err != nil {
		if rbErr := tx.Rollback(ctx); rbErr != nil {
			return fmt.Errorf("rolling back after error %q: %w", err, rbErr)
		}
		return err
	}

	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("committing transaction: %w", err)
	}
	return nil
}

// IsUniqueViolation checks if the given error is a PostgreSQL unique constraint violation.
func IsUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}
