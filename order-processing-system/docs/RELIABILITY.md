# RELIABILITY

This document defines reliability expectations and runbook-level controls.

## Reliability Objectives
- Preserve correctness of order state transitions.
- Maintain predictable degradation under load or partial outage.
- Support rapid diagnosis and safe recovery.

## Core Patterns in This System
- Outbox pattern for transactional event publication.
- Multi-layer idempotency (gateway, consumers, saga).
- DLQ + replay for failed event recovery.
- Temporal durable workflow execution for migrated sagas.
- Rate limiting and load shedding at gateway.
- Edge resilience via Envoy controls.

## Reliability Checklist for Changes
- Have new failure modes been identified?
- Is duplicate processing prevented?
- Are retries bounded and observable?
- Is fallback behavior explicit for dependency failures?
- Are DLQ/replay implications documented?

## Diagnostics Entry Points
- Health/status: `make status`, service `/health` endpoints.
- Tracing/metrics/logs: `make jaeger`, `make prometheus`, `make grafana`, `make logs`.
- Messaging: `make kafka-ui`, `make dlq-ui`, replay commands.

## References
- [Resilience](./resilience.md)
- [Observability](./observability.md)
- [Event Versioning](./event_versioning.md)
- [Architecture Blueprint](../ARCHITECTURE.md)
