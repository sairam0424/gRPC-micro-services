# Decision Records

Use this file as an index for architecture and process decisions.

## ADR Format
- ID
- Date
- Decision statement
- Context
- Consequences
- Status (Accepted, Superseded, Deprecated)

## Seed Decisions
| ADR ID | Decision | Status | Source |
|---|---|---|---|
| ADR-001 | Split runtime into data and control planes via compose topology | Accepted | `docker-compose-data.yml`, `docker-compose-control.yml` |
| ADR-002 | Use protobuf contracts + schema registry for event interface governance | Accepted | `proto/`, `docs/event_versioning.md` |
| ADR-003 | Enforce multi-layer idempotency and DLQ replay for reliability | Accepted | service code + `docs/resilience.md` |
| ADR-004 | Treat AGENTS/ARCHITECTURE/PLANS as canonical contributor entrypoints | Accepted | docs harness implementation |
| ADR-TEMP-* | Temporal migration decisions for saga orchestration | Accepted | `docs/decision-log-temporal-migration.md` |

## Next Step
Create dedicated ADR files if decision volume grows; keep this index as root navigator.
