# SECURITY

This document captures minimum security expectations for contributors.

## Security Objectives
- Protect user identity and authentication material.
- Prevent unauthorized order and inventory operations.
- Reduce blast radius from service compromise.

## Baseline Controls
- JWT-based route protection on gateway-authenticated paths.
- Environment-based secret management (`.env`, compose env vars).
- Service separation across control/data concerns.
- Dependency and runtime hardening through containerized service boundaries.

## Secure Change Checklist
- Auth/Authz: does the change alter authentication, authorization, or token handling?
- Data exposure: does the change log or return sensitive values?
- Transport: are service endpoints and internal channels appropriately scoped?
- Storage: are persistence and cache keys safe and non-leaking?
- Dependency risk: were new packages/images introduced and reviewed?

## Incident-Oriented Rules
- Prefer fail-closed behavior on auth failures.
- Preserve auditability through logs/traces without exposing secrets.
- Document compensating controls for known security debt.

## References
- [AGENTS](../AGENTS.md)
- [Reliability](./RELIABILITY.md)
- [Resilience](./resilience.md)
