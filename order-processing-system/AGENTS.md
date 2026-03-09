# AGENTS: Harness Operating Contract

This file is the canonical operating contract for agents and humans working in `order-processing-system`.

## Mission
Ship reliable changes to a distributed order-processing platform with minimal ambiguity.

Core outcomes:
- Reduce information barrier: quickly find trustworthy context.
- Reduce entropy: keep architecture, specs, and plans synchronized with code.
- Increase iteration speed: enforce deterministic workflows and verification gates.

## Golden Rule: Source of Truth Order
Before editing code, load context in this order:
1. `AGENTS.md` (this file)
2. `ARCHITECTURE.md`
3. `README.md`
4. The relevant product spec in `docs/product-specs/`
5. Existing technical deep docs in `docs/*.md`
6. Proto contracts in `proto/**`
7. Actual service code

If any conflict exists, prefer:
1. Running code
2. Proto contracts
3. Compose/runtime configs
4. Documentation

## Repository Map
- `api-gateway/`: FastAPI entrypoint, REST-to-gRPC bridge, SSE, auth, rate limiting, load shedding.
- `order-service/`: Go gRPC service, order persistence, outbox, Kafka producer/consumer, saga hooks.
- `inventory-service/`: FastAPI + gRPC inventory, DB + cache/filter layers, Kafka consumers/producers.
- `order-streamer/`: Go Kafka consumer + gRPC streaming server.
- `saga-orchestrator/`: Go saga orchestration engine and control flow.
- `auth-service/`: FastAPI auth and user management.
- `media-service/`: FastAPI media metadata and object-store integration.
- `proto/`: gRPC and event contracts.
- `docs/`: design, plans, reliability/security, and references.
- `docker-compose-data.yml`, `docker-compose-control.yml`: data/control plane runtime topology.

## Service Ownership Map (Code Responsibility)
Use this map for routing changes and review focus.

| Domain | Primary Paths | Primary Responsibilities |
|---|---|---|
| Ingress/API | `api-gateway/src/app` | Authn/authz checks, HTTP contracts, SSE fanout, resilience middleware |
| Order lifecycle | `order-service/internal` | Order write path, status transitions, outbox, idempotent event handling |
| Inventory lifecycle | `inventory-service/src/app` | Stock consistency, reservation/release logic, filter/cache correctness |
| Streaming | `order-streamer/` | Event-to-stream translation and live update delivery |
| Orchestration | `saga-orchestrator/internal` | Cross-service transaction choreography and compensations |
| Identity | `auth-service/src/app` | User identity, JWT lifecycle, auth DB model |
| Media | `media-service/src/app` | Media metadata integrity and event publication |
| Contracts | `proto/**` | Backward-compatible interface evolution |
| Runtime | `docker-compose-*.yml`, `proxy/**`, `infra/**` | Plane boundaries, observability, infra health |

## Standard Workflow
1. Intake
- Restate target behavior and affected services.
- Identify whether change is behavior, interface, or infra-only.

2. Context load
- Load the minimum docs and code needed from the source-of-truth order.
- Confirm current runtime assumptions using compose/proto/code.

3. Plan
- Write/update execution plan in `docs/exec-plans/active/` before implementation for non-trivial work.
- Link the plan to one or more product specs.

4. Implement
- Prefer small, reversible changes.
- Keep contracts explicit and backward compatible.

5. Validate
- Run targeted checks relevant to touched domains.
- Verify docs/spec/plan updates are complete.

6. Close
- Move completed plan to `docs/exec-plans/completed/`.
- Update quality and tech debt trackers.

## Command Catalog
Use these commands as canonical local operations.

### Core lifecycle
- `make generate`: regenerate gRPC/proto artifacts and tidy modules.
- `make up-dev`: start full stack in development mode.
- `make down`: stop the stack.
- `make status`: inspect container status.
- `make logs`: follow logs across data/control planes.

### Validation
- `make test`: end-to-end order flow smoke test.
- `make test-resilience`: verify rate limiting and load shedding behavior.

### Data and events
- `make seed`: generate synthetic traffic.
- `make cdc-setup`: register Debezium connectors.
- `make kafka-dlq-topics`: create DLQ topics.
- `make replay-inventory`, `make replay-order-streamer`, `make replay-analytics`: replay failed events.

### Observability and diagnosis
- `make jaeger`, `make prometheus`, `make grafana`, `make kafka-ui`, `make dlq-ui`, `make envoy-admin`.
- `make analytics-logs`, `make media-logs`, `make flink-logs`, `make cdc-logs`.

## Information Barrier Controls
Never begin implementation before locating these facts:
- API/grpc contract: under `proto/**`.
- Runtime dependency path: from `docker-compose-data.yml` and `docker-compose-control.yml`.
- State model and persistence: from service model files.
- Existing resilience behavior: `docs/resilience.md`, middleware/services.
- Existing observability signals: `docs/observability.md`, metrics and tracing code.

Prohibited behavior:
- Guessing event schemas or topic names without checking code/proto.
- Updating only one service when contract change affects multiple consumers.
- Declaring behavior complete without a matching test or validation command.

## Entropy Control Rules
When behavior changes, update all applicable artifacts in the same change set:
- Product behavior -> `docs/product-specs/*`.
- Execution approach/status -> `docs/exec-plans/*`.
- Reliability/security posture -> `docs/RELIABILITY.md` / `docs/SECURITY.md`.
- Quality evaluation -> `docs/QUALITY_SCORE.md`.
- Debt intentionally accepted -> `docs/exec-plans/tech-debt-tracker.md`.
- Architecture behavior -> `ARCHITECTURE.md` and/or design docs.

If a change does not require one of the above, explicitly record why in the PR description or plan note.

## Interface and Contract Discipline
- Prefer additive protobuf changes; avoid breaking field/tag reuse.
- Reserve removed field tags; never repurpose old tags.
- Keep topic naming and event type semantics stable unless migration is planned.
- For idempotency-related changes, document dedupe key shape and storage location.

## Done Criteria
A change is done only if all are true:
- Behavior implemented and validated for touched service paths.
- Contract impacts checked against `proto/**` and downstream consumers.
- Docs/specs/plans updated under entropy control rules.
- No unresolved ambiguity about runtime topology or ownership.

## Related References
- [System Blueprint](./ARCHITECTURE.md)
- [Plans Playbook](./docs/PLANS.md)
- [Design Docs Index](./docs/design-docs/index.md)
- [Reliability](./docs/RELIABILITY.md)
- [Security](./docs/SECURITY.md)
