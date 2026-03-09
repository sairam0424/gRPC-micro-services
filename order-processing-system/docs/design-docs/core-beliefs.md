# Core Beliefs

These beliefs define how we design, implement, and operate changes in this repository.

## 1. Contracts Before Code
- Protobuf and event schemas are first-class interfaces.
- Breaking changes require explicit migration strategy; default is backward-compatible evolution.

## 2. Determinism Over Heroics
- Repeatable build/run/test workflows beat one-off fixes.
- Every meaningful change should be traceable through a plan and validation path.

## 3. Entropy Is a Production Risk
- Stale docs and stale specs create operational defects.
- If behavior changes, update architecture/spec/plan/debt/quality artifacts in the same change stream.

## 4. Distributed Systems Need Explicit Failure Design
- Success paths are insufficient; compensation, idempotency, and replay are mandatory concerns.
- Failure-domain awareness is required for all cross-service changes.

## 5. Minimize Context Load for Contributors
- Critical decisions must be discoverable in canonical files.
- Contributors should not need private tribal knowledge to make safe changes.

## 6. Measure Reliability, Do Not Assume It
- Reliability claims need telemetry and verifiable checks.
- Operational playbooks are part of deliverable quality.

## 7. Security Is Continuous, Not a Final Step
- Threat-aware defaults and least-privilege boundaries apply during design and implementation.
- Sensitive data movement and authentication behavior must be explicit and reviewable.

## 8. Optimize for Safe Iteration Speed
- Small, reversible, well-documented increments outperform large opaque refactors.
- Fast feedback loops (`make test`, observability checks) are mandatory for stable velocity.

## Decision Heuristics
When multiple approaches are viable, prioritize in this order:
1. Preserves interface compatibility.
2. Improves operability and failure recovery.
3. Reduces total system complexity.
4. Improves performance without weakening correctness.
5. Improves contributor speed through clearer docs and tooling.

## Related
- [AGENTS](../../AGENTS.md)
- [ARCHITECTURE](../../ARCHITECTURE.md)
- [Architecture Constraints](./architecture-constraints.md)
