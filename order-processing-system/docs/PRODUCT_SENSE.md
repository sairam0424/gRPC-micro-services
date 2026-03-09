# PRODUCT_SENSE

This document captures product heuristics for prioritizing and shaping work.

## Product Heuristics
- Favor user-visible reliability over feature breadth.
- Reduce time-to-confidence for first-time users.
- Prefer transparent state transitions over implicit background behavior.
- Design for degraded operation, not only ideal paths.

## Decision Questions
Before approving a behavior change, answer:
- Which user pain is reduced?
- What failure case gets better or worse?
- Does this simplify or complicate the user mental model?
- Can we measure success within one release cycle?

## Priority Model
1. Reliability and correctness of order lifecycle.
2. Onboarding and first-order success rate.
3. Operator visibility and incident recovery speed.
4. Throughput and performance improvements.

## Related
- [New User Onboarding Spec](./product-specs/new-user-onboarding.md)
- [Reliability](./RELIABILITY.md)
- [Quality Score](./QUALITY_SCORE.md)
