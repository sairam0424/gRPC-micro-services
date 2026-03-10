# Decision Log: Temporal Saga Migration

## ADR-TEMP-001
- Date: 2026-03-11
- Decision:
  - Use self-hosted Temporal OSS (Docker Compose) for saga orchestration.
- Context:
  - Existing custom orchestrator lacks durable execution history and declarative retry semantics.
- Consequences:
  - Adds Temporal infrastructure dependencies.
  - Provides durable workflow execution and first-class workflow auditability.
- Status: Accepted

## ADR-TEMP-002
- Date: 2026-03-11
- Decision:
  - Keep `SagaService` gRPC contract stable and introduce internal route-based backend selection.
- Context:
  - Migration must be incremental and low-risk without breaking existing APIs.
- Consequences:
  - Runtime adds `legacy|temporal|canary` selection complexity.
  - Enables fast rollback through configuration.
- Status: Accepted

## ADR-TEMP-003
- Date: 2026-03-11
- Decision:
  - Implement Temporal activities by reusing existing Kafka command/event path (`reserve_stock`, `complete_order`, `release_stock`, `fail_order`) for Phase 1-3.
- Context:
  - Existing business logic and idempotency already live in command consumers in order/inventory services.
- Consequences:
  - Preserves current service boundaries and compensation behavior.
  - Temporal worker requires Kafka access.
- Status: Accepted

## ADR-TEMP-004
- Date: 2026-03-11
- Decision:
  - Use deterministic workflow IDs (`order-saga-{orderId}`) with Redis route persistence (`saga:route:{workflowID}`).
- Context:
  - Migration requires stable idempotency and consistent status lookup across backends.
- Consequences:
  - Simplifies replay-safe starts and rollback routing.
  - Requires route key management in Redis.
- Status: Accepted

## ADR-TEMP-005
- Date: 2026-03-11
- Decision:
  - Default route remains `legacy` until explicitly switched.
- Context:
  - Prevent accidental behavioral change in production during rollout.
- Consequences:
  - Temporal path is opt-in.
  - Rollout requires config change and operational verification.
- Status: Accepted
