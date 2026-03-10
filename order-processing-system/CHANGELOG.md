# Changelog

## 2026-03-11

### Added
- Temporal OSS self-hosted stack in compose:
  - `temporal-postgresql`, `temporal`, `temporal-ui`, `temporal-worker`.
- Saga orchestrator routing layer for incremental migration:
  - `legacy`, `temporal`, and `canary` route modes via `SAGA_ROUTE_ORDER_FULFILLMENT`.
- Temporal workflow implementation for `order_fulfillment`:
  - `OrderFulfillmentWorkflow` with forward steps and explicit compensation.
- Temporal activity worker bridge using existing Kafka saga command/event contracts.
- Saga workflow/activity tests including compensation and retry behavior.
- New Make targets:
  - `temporal-up`, `temporal-down`, `temporal-ui`, `temporal-logs`.

### Changed
- `saga-orchestrator` now supports runtime modes:
  - `SAGA_RUNTIME_MODE=api|worker|all`.
- Saga command/event topics are now configurable by environment:
  - `SAGA_COMMAND_TOPIC`, `SAGA_EVENT_TOPIC`.
- `order-service` and `inventory-service` saga topic wiring updated to read env topic names.
- `GetSagaStatus` now resolves both legacy and Temporal-backed workflow status.

### Notes
- Default routing remains `legacy` to preserve current behavior.
- Legacy orchestrator remains available for rollback.
