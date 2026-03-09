# Architecture Constraints

These constraints are mandatory unless an explicit approved exception exists.

## Contract Constraints
- Protobuf interfaces are authoritative for gRPC APIs.
- Event schema evolution must remain backward-compatible by default.
- Removed proto fields must not have tag reuse.

## Runtime Constraints
- Request-path services should not gain hidden control-plane coupling.
- Critical flows must preserve idempotency guarantees.
- Health and observability signals must remain available under degraded modes.

## Data and State Constraints
- Order and inventory state transitions must be explicit and traceable.
- Cache/filter layers must not become silent sources of incorrect stock state.
- DLQ usage must preserve replayability and message provenance.

## Security Constraints
- Protected routes require explicit auth checks.
- Secrets must not be hard-coded or logged.
- Cross-service trust assumptions should be documented and minimal.

## References
- [Architecture Blueprint](../../ARCHITECTURE.md)
- [Event Versioning](../event_versioning.md)
- [Resilience](../resilience.md)
