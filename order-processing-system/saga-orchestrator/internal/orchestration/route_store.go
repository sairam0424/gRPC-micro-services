package orchestration

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

type RedisRouteStore struct {
	client *redis.Client
	ttl    time.Duration
}

func NewRedisRouteStore(client *redis.Client, ttl time.Duration) *RedisRouteStore {
	if ttl <= 0 {
		ttl = 7 * 24 * time.Hour
	}
	return &RedisRouteStore{client: client, ttl: ttl}
}

func (s *RedisRouteStore) key(workflowID string) string {
	return fmt.Sprintf("saga:route:%s", workflowID)
}

func (s *RedisRouteStore) Set(ctx context.Context, workflowID string, route string) error {
	if workflowID == "" {
		return nil
	}
	return s.client.Set(ctx, s.key(workflowID), route, s.ttl).Err()
}

func (s *RedisRouteStore) Get(ctx context.Context, workflowID string) (string, error) {
	if workflowID == "" {
		return "", ErrSagaNotFound
	}
	val, err := s.client.Get(ctx, s.key(workflowID)).Result()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return "", ErrSagaNotFound
		}
		return "", err
	}
	return val, nil
}
