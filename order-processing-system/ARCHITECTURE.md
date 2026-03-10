# ARCHITECTURE: Order Processing System Blueprint

This document is the canonical architecture context for agents and contributors.

## 1. System Model
The platform is an event-driven microservice system with gRPC for synchronous service contracts and Kafka for asynchronous state propagation.

Primary capabilities:
- Order creation and lifecycle management.
- Inventory reservation with consistency protections.
- Real-time order status streaming to clients.
- Saga-based orchestration and compensations.
- CDC, analytics, search, and observability integration.

## 2. Runtime Topology

### Ingress and edge
- Nginx proxy routes web and API traffic.
- Envoy load balances and applies edge resilience policies.
- API Gateway replicas provide REST endpoints, authentication checks, and gRPC fan-out.

### Core business services
- Order Service (Go): writes orders, outbox events, reacts to inventory/media events.
- Inventory Service (Python): stock reservation/release, cache and filter layers, Kafka event handling.
- Order Streamer (Go): consumes order events and serves gRPC streaming updates.
- Saga Orchestrator (Go): manages saga state and cross-service command flow; supports legacy and Temporal-backed routing.
- Temporal Worker (Go): executes Temporal workflows/activities for migrated sagas.
- Auth Service (Python): user identity and JWT flow.
- Media Service (Python): media metadata and event propagation.

### State and messaging
- PostgreSQL/Neon: transactional stores for order, inventory, auth, media.
- Redis Stack: rate limiting, filters, cache, and idempotency keys.
- Kafka: event bus for domain and control events.
- Schema Registry: protobuf schema governance.
- Debezium Connect: CDC bridge from DB WAL to Kafka.

### Observability
- OpenTelemetry Collector receives traces/metrics/logs.
- Jaeger, Prometheus, Loki, Grafana for telemetry analysis.
- Kafka UI, DLQ UI, and additional admin UIs for operations.

## 3. Plane Isolation: Data vs Control
Compose files split operational concerns into two planes.

Data plane (`docker-compose-data.yml`):
- Request handling services and core data paths.
- Primary event producers/consumers and user-facing dependencies.

Control plane (`docker-compose-control.yml`):
- Governance/orchestration/CDC/observability services.
- Schema management, replay tooling, and monitoring.

Integration rule:
- Cross-plane connectivity must be explicit and justified.
- Service should prefer same-plane dependencies unless governance or telemetry requires crossing.

## 4. Contract Map
### gRPC contracts (`proto/**`)
- `order/v1/order.proto`: create/get/list order APIs.
- `inventory/v1/inventory.proto`: check/reserve/release/update/list inventory.
- `stream/v1/stream.proto`: server-side streaming for order updates.
- `saga/v1/saga.proto`: saga start and status lookup.

### Event contracts (`proto/events/v1/events.proto`)
Primary event payloads include:
- `OrderCreatedEvent`
- `InventoryReservedEvent`
- `InventoryFailedEvent`
- `InventoryUpdatedEvent`
- `MediaUploadedEvent`

Event handling rule:
- Treat event_type values and field semantics as stable interfaces.
- Maintain backward compatibility through additive schema evolution.

## 5. Event Lifecycle and Processing Paths
Nominal order flow:
1. Client sends order request to API Gateway.
2. Gateway invokes Order Service gRPC.
3. Order Service persists order and outbox record.
4. Outbox/Kafka publishes order domain event.
5. Inventory Service consumes and attempts stock reservation.
6. Inventory success/failure event is emitted.
7. Order Service consumes inventory result and updates status.
8. Order update events are streamed via Order Streamer and surfaced to clients through SSE.

Saga control flow:
- Saga Orchestrator emits commands (reserve/complete/release/fail).
- Services handle commands idempotently and publish saga events.
- Orchestrator advances/compensates based on event status.
- Temporal-routed sagas execute in durable workflows while preserving the same command/event side effects.

## 6. Idempotency Model
Idempotency is enforced at multiple layers:
- API Gateway: request dedupe via idempotency key patterns and rate-limiting controls.
- Order/Inventory consumers: `processed_events` persistence to prevent duplicate Kafka processing.
- Saga engine: redis keys for command/status dedupe.
- Outbox: transactional event publication to avoid dual-write inconsistency.

Required change discipline:
- Any change to dedupe key shape, TTL, or storage scope must be documented in `docs/RELIABILITY.md` and relevant execution plan.

## 7. Failure Domains and Resilience Patterns
Failure domains:
- Ingress saturation and upstream instability.
- Broker or schema-registry unavailability.
- Partial DB/cache outages.
- Consumer lag and DLQ growth.

Implemented patterns:
- Rate limiting and load shedding in API Gateway.
- Envoy resilience controls (circuit breaking/outlier handling/retry controls).
- DLQ + replay services for recovery.
- Cache-aside and filter strategy for inventory hot path.
- Distributed tracing and metrics-based diagnostics.

## 8. Operational Diagnostics Entry Points
Primary runbook commands:
- `make status`, `make logs`
- `make jaeger`, `make prometheus`, `make grafana`
- `make kafka-ui`, `make dlq-ui`, `make cdc-logs`
- `make test`, `make test-resilience`

Primary doc references:
- `docs/resilience.md`
- `docs/observability.md`
- `docs/analytics_pipeline.md`
- `docs/event_versioning.md`

## 9. Architecture Invariants
- Proto contracts are authoritative for service interfaces.
- Event schemas evolve backward-compatibly.
- Order state transitions are observable through events and stream APIs.
- Control-plane services do not become hidden runtime dependencies for hot request paths.
- Documentation and plan artifacts must remain synchronized with behavior changes.

## 10. Deep References
- [Existing Architecture Guide](./docs/architecture.md)
- [Architecture Diagram](./docs/architecture_diagram.md)
- [Resilience](./docs/resilience.md)
- [Observability](./docs/observability.md)
- [Event Versioning](./docs/event_versioning.md)
