# Product Spec: New User Onboarding

## Problem Statement
A new user must move from first visit to a successful first order with confidence, visibility, and minimal friction.

## User Value
- Fast account creation and login.
- Clear ordering workflow.
- Real-time feedback on order status.
- Trust through transparent failures and retries.

## Scope
In scope:
- Signup and login using auth endpoints.
- Authenticated order creation via API gateway.
- Live order status updates via SSE stream path.
- Basic order search and visibility in dashboard.

Out of scope:
- Social login providers.
- Payments and refunds UX.
- Multi-factor authentication UX.
- Mobile-native app-specific onboarding.

## User Journey
1. User lands on web client.
2. User signs up or logs in.
3. User views available inventory context.
4. User creates first order.
5. User sees pending -> processing -> completed/failed status updates in near real time.
6. User can locate order via list/search and inspect status details.

## Functional Requirements
- Auth
  - Signup persists user and returns access token.
  - Login validates credentials and returns access token.
- Order creation
  - Authenticated `POST /api/orders` creates order through gRPC path.
  - Request failures return actionable error payloads.
- Live updates
  - `GET /api/orders/events` provides server-sent updates for user-visible order status.
  - Stream reconnect behavior should not duplicate visible records unexpectedly.
- Visibility
  - User can list/retrieve own orders.
  - Search endpoint returns relevant results when enabled.

## Error/Fallback Requirements
- Auth errors: clear invalid credential or token-expired response.
- Inventory reservation failure: order transitions to failed state with reason.
- Stream interruptions: frontend reconnect strategy with graceful status messaging.
- Partial platform degradation: health and status endpoints remain observable.

## Reliability and Security Requirements
- Idempotency: order operations avoid duplicate side effects under retries.
- JWT validation enforced for protected routes.
- Critical state transitions are observable in logs/traces.
- Sensitive fields are not leaked in user-visible error payloads.

## Telemetry and Success Metrics
Primary success metrics:
- Signup-to-first-order conversion rate.
- First-order completion rate.
- Median and P95 time from order creation to terminal status.
- SSE connection success/reconnect rates.

Operational metrics:
- `ratelimit_rejects_total`, `loadshed_rejects_total`.
- Order/inventory event lag and DLQ counts.
- Gateway/auth service health signal stability.

## Acceptance Criteria
- A new user can create an account and authenticate successfully.
- Authenticated user can create an order through gateway API.
- Order status updates are visible in real time until terminal state.
- Failed inventory path is visible to user and recorded in system telemetry.
- Existing docs and execution plan are updated for any onboarding behavior changes.

## Dependencies
- Auth service availability.
- API gateway routing and JWT validation.
- Order, inventory, streamer, and Kafka event paths.
- Proxy routing and frontend integration.

## References
- [Frontend Integration](../frontend_integration.md)
- [Architecture](../architecture.md)
- [Observability](../observability.md)
- [Resilience](../resilience.md)
