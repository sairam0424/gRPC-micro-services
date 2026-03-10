# Temporal Saga Runbook

## Scope
Local/self-hosted operation for Temporal-backed saga execution in `order-processing-system`.

## Services
- Temporal Server: `temporal` (`localhost:7233`)
- Temporal UI: `temporal-ui` (`http://localhost:8233`)
- Temporal Worker: `temporal-worker`
- Saga API: `saga-orchestrator` (gRPC `:50054`)

## Start
Prerequisites:
- `docker.env` exists at repo root for `docker-compose.dev.yml` runs.

1. Start full stack:
   - `make up-dev`
2. Or start Temporal-only control services:
   - `make temporal-up`
3. Check Temporal UI:
   - `make temporal-ui`

## Routing Modes
Configure in saga-orchestrator environment:
- `SAGA_ROUTE_ORDER_FULFILLMENT=legacy`
- `SAGA_ROUTE_ORDER_FULFILLMENT=temporal`
- `SAGA_ROUTE_ORDER_FULFILLMENT=canary`
- `SAGA_CANARY_PERCENT=0..100`

Default is `legacy`.

## Required Env
- `SAGA_COMMAND_TOPIC` (default: `saga-commands`)
- `SAGA_EVENT_TOPIC` (default: `saga-events`)
- `TEMPORAL_ADDRESS` (default: `temporal:7233`)
- `TEMPORAL_NAMESPACE` (default: `default`)
- `TEMPORAL_TASK_QUEUE_ORDER` (default: `saga.order.fulfillment`)

## Validate Migration
1. Set route to Temporal:
   - `SAGA_ROUTE_ORDER_FULFILLMENT=temporal`
2. Restart `saga-orchestrator`.
3. Create an order via existing API flow.
4. In Temporal UI, verify workflow ID format:
   - `order-saga-{orderId}`
5. Use `GetSagaStatus` and confirm status/task/output fields update.

## Logs
- `make temporal-logs`
- `make logs`

## Rollback
1. Set `SAGA_ROUTE_ORDER_FULFILLMENT=legacy`.
2. Restart `saga-orchestrator`.
3. Keep `temporal-worker` running until in-flight workflows complete (or terminate manually in Temporal UI).

## Known Notes
- Temporal activities currently reuse existing Kafka command/event saga handlers.
- Topic mismatch is mitigated by using shared env topic variables across orchestrator/order/inventory services.
