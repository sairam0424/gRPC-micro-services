# DESIGN

This document defines how design decisions should be made and documented for this repository.

## Design Principles
- Contract-first design: update proto/event contracts before implementation details.
- Observable behavior: every important flow should expose trace/metric/log evidence.
- Progressive hardening: start simple, then harden with reliability and security controls.
- Low-entropy docs: design intent must remain synchronized with running behavior.

## Design Inputs
Use these as mandatory context before major design changes:
- [AGENTS](../AGENTS.md)
- [ARCHITECTURE](../ARCHITECTURE.md)
- [Core Beliefs](./design-docs/core-beliefs.md)
- [Architecture Constraints](./design-docs/architecture-constraints.md)

## Design Review Checklist
- Is the contract impact explicit and backward-compatible?
- Are failure modes and compensations specified?
- Are observability and security controls addressed?
- Is plan/spec/doc synchronization captured?

## Deep References
- [Architecture](./architecture.md)
- [Resilience](./resilience.md)
- [Observability](./observability.md)
