# Plan: Temporal Saga Migration (Phases 1-3)

## Metadata
- Date: 2026-03-11
- Owner: Codex
- Linked spec(s):
  - `docs/product-specs/new-user-onboarding.md` (order lifecycle reliability impact)
- Status: Completed (Phases 1-3)

## Problem and Goal
- Problem:
  - Current saga orchestration is Redis + Kafka command/event driven with no durable workflow history, no declarative retry policy, and limited compensation observability.
- Desired outcome:
  - Add Temporal OSS orchestration with migration-safe routing so selected sagas run on Temporal while legacy orchestrator remains available.

## Scope
In scope:
- Phase 1: Temporal infrastructure and bootstrap.
- Phase 2: Runtime routing layer for `legacy|temporal|canary` saga execution.
- Phase 3: Migrate `order_fulfillment` saga into Temporal workflow + activities.
- Tests for workflow logic, activities, and end-to-end workflow execution in Temporal testsuite.
- Docs and runbook updates for local operation.

Out of scope:
- Full migration of all sagas.
- Legacy orchestrator retirement.
- Kubernetes deployment manifests.

## Implementation Approach
- Affected subsystems:
  - `saga-orchestrator` (core runtime and Temporal worker).
  - `order-service` and `inventory-service` (topic env wiring compatibility).
  - `docker-compose-control.yml`, `docker-compose.dev.yml`, `docker-compose-data.yml`, `Makefile`.
- Contract/API impact:
  - No public gRPC API changes for `SagaService`.
  - Additive env/config only.
- Data/model impact:
  - Introduce route persistence key in Redis: `saga:route:{workflowID}`.
  - Temporal workflow history becomes source-of-truth for Temporal-routed executions.
- Risky changes and mitigation:
  - Topic mismatch risk mitigated by env-based saga topic configuration in orchestrator/order/inventory.
  - Migration risk mitigated by default route `legacy` and reversible routing flag.
  - Compensation correctness covered with dedicated workflow tests.

## Validation Plan
- Unit/integration checks:
  - `cd saga-orchestrator && go test ./...`
- Manual/system checks:
  - Bring up stack with Temporal services.
  - Create order, verify Temporal UI run details.
  - Verify `GetSagaStatus` for both legacy and temporal workflow IDs.
- Observability checks:
  - Validate workflow history in Temporal UI includes retries and compensation steps.
  - Validate logs include `workflowId`, `runId`, `sagaId`, `orderId`.

## Rollback/Fallback
- Rollback method:
  - Set `SAGA_ROUTE_ORDER_FULFILLMENT=legacy`, restart `saga-orchestrator`.
- Data safety considerations:
  - Legacy path is unchanged and retained.
  - No destructive schema migrations.

## Completion Criteria
- Temporal stack is runnable locally.
- `saga-orchestrator` supports route-based execution and worker runtime.
- `order_fulfillment` saga executes in Temporal with explicit compensation behavior.
- Tests covering happy path, failure/compensation, and retry behavior pass.
- Changelog + decision log + runbook updates completed.

## Phase 4-6 TODO Roadmap
- Phase 4 (validation/observability):
  - Add Temporal-specific dashboards and alert thresholds.
  - Add workflow failure/compensation operational playbook.
- Phase 5 (remaining sagas):
  - Add saga registry and repeat migration template per saga.
  - Enable per-saga route flags.
- Phase 6 (legacy retirement):
  - Freeze legacy starts, drain in-flight runs, and remove legacy loop.
