# Caching & Observability Architecture

This document provides a deep dive into the caching strategies and observability tools implemented in the Order Processing System.

## 1. Caching Strategy: Advanced Cache-Aside

The `inventory-service` implements a robust multi-tiered caching architecture.

### Event-Driven Invalidation Pipeline
We follow the **Golden Rule** of caching: *Invalidate via events, not TTL alone.*

1.  **State Change**: An atomic stock reservation or manual update occurs in the PostgreSQL database.
2.  **Event Broadcast**: The `Inventory Service` publishes an `inventory.updated` event to the `order-events` Kafka topic.
3.  **Synchronized Refresh**: Every instance of the `Inventory Service` (and potentially other downstream consumers) receives the event and updates its local/shared Redis cache entry.
4.  **Consistency**: This ensures that even in a scaled environment, all cache nodes are updated nearly simultaneously, minimizing stale data windows.

### Resilience Patterns

#### Single-flight (Request Coalescing)
To prevent a **Cache Stampede** (where a cache miss triggers thousands of simultaneous DB queries), we use the Single-flight pattern.
- If multiple requests for `PROD-001` occur during a cache miss, only the first request proceeds to the database.
- Subsequent requests wait for the first one to finish and then serve from the newly populated cache.

#### TTL Jitter
To prevent a **Thundering Herd** (where many items expire at the same time), we add a random jitter (0-300 seconds) to the default 1-hour TTL. This staggers the expiration and subsequent re-population load on the database.

## 2. Observability Stack

### Metrics (Prometheus + OTel)
We track real-time performance using OpenTelemetry Gauges and Counters:
- `inventory.cache.hits`: Total successful cache lookups.
- `inventory.cache.misses`: Total lookups requiring a database hit.
- **Grafana Panel**: A smooth, real-time "Hits vs Misses" graph is available in the System Overview dashboard.

### Tracing (Jaeger)
Every cache lookup is part of a distributed trace. If a request is slow, you can see exactly where the time was spent:
- Cache Check (Redis latency)
- Single-flight Wait
- DB Query (SQL execution time)

## 3. Management Suite

### RedisInsight
The "Source of Truth" for Redis. Use it to:
- Inspect the **Bloom Filter** (Tier-1) and **Cuckoo Filter** (Tier-2) structures.
- Analyze memory fragmentation and key distribution.
- Use the **Profiler** to see every command hits the cache.

### Redis Commander
A lightweight alternative for quick data manipulation. Best for:
- Manual stock corrections during development.
- Searching for specific keys across multiple Redis databases.
