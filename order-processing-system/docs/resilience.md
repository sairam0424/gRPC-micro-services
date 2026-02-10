# Resilience Documentation

This document describes the resilience patterns implemented at the API Gateway level to ensure system stability and protect downstream services.

## Rate Limiting (Token Bucket)

The system implements a centralized rate limiter using Redis and the **Token Bucket** algorithm.

### Implementation Details
- **Storage**: Redis (centralized for multi-instance scalability).
- **Algorithm**: Token Bucket implemented via an atomic Lua script for performance and precision.
- **Identification**:
    - **Authenticated Users**: Limited by `user_id` extracted from JWT.
    - **Unauthenticated/Anonymous**: Limited by Client IP address.

### Default Limits
| Scope | Capacity | Fill Rate | Description |
|-------|----------|-----------|-------------|
| User  | 100      | 1.66 rps  | ~100 requests per minute |
| IP    | 1000     | 16.6 rps  | ~1000 requests per minute |

### Response Headers
When successful, responses include:
- `X-RateLimit-Limit`: The total capacity of the bucket.
- `X-RateLimit-Remaining`: The number of tokens left in the bucket.

### Rejection
When a limit is exceeded, the API returns `429 Too Many Requests` with:
- `Retry-After`: Number of seconds to wait until enough tokens are available.

---

## Load Shedding

Load shedding protects the system under extreme stress by rejecting non-critical requests while keeping core functionality alive.

### Priority Levels
- **CRITICAL**: Always prioritize. Examples: `POST /orders`, `/health`.
- **NON-CRITICAL**: Rejection candidate under stress. Examples: `GET /inventory`, `GET /orders`, `GET /me`.

### Stress Triggers
The Load Shedder can be triggered by:
- High CPU/Memory usage.
- Request queue depth.
- Backend latency spikes.

### Shedding Logic
| Stress Level | Action |
|--------------|--------|
| < 0.5 (Normal) | Allow all requests. |
| 0.5 - 0.8 (Medium) | Reject non-critical read operations (`GET /inventory`, `GET /orders`). |
| > 0.8 (High) | Reject all non-critical requests. |

### Response
Returns `503 Service Unavailable` with a descriptive message.

---

## Visualization & Monitoring

The system exposes real-time resilience metrics and provides visualization via Redis Insight.

### Metrics Exposed
Historical and real-time counters are tracked in Redis and exposed via the API Gateway's `/metrics/filters` endpoint.

| Metric | Redis Key | Description |
|--------|-----------|-------------|
| Rate Limit Hits | `metrics:ratelimit_hits` | Total requests allowed by the rate limiter. |
| Rate Limit Rejects | `metrics:ratelimit_rejects` | Total requests rejected with 429. |
| Load Shed Rejects | `metrics:loadshed_rejects` | Total requests rejected with 503 under stress. |

### Viewing in Redis Insight
1. Open Redis Insight: `make redis-insight` (or go to `http://localhost:8003`).
2. Search for keys prefix with `metrics:`.
3. You can create a **Browser** view to watch these counters increment in real-time as you load the system.

### Verification Script
You can run the built-in verification tool to see these features in action:
```bash
make test-resilience
```
