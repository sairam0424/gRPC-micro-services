# PLANS

This file defines execution planning discipline for contributors.

## Execution Workflow
1. Pick or write a product spec in `docs/product-specs/`.
2. Create active plan using `docs/exec-plans/active/PLAN_TEMPLATE.md`.
3. Implement in bounded increments with validation evidence.
4. Close via `docs/exec-plans/completed/COMPLETION_TEMPLATE.md`.
5. Update quality score and tech debt entries.

## Planning Standards
- Plans must be decision-complete.
- Plans must include failure handling and rollback path when risk exists.
- Plans must include explicit acceptance criteria and validation steps.

## Required Linkage
Every substantial change should link:
- 1+ product spec
- 1 active/completed plan
- Quality/debt updates when relevant

## References
- [Execution Plans Index](./exec-plans/index.md)
- [Product Specs Index](./product-specs/index.md)
- [Quality Score](./QUALITY_SCORE.md)
