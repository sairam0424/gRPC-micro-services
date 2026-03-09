# QUALITY_SCORE

Use this scorecard to assess release readiness and documentation completeness.

## Weighted Score Model (100 points)
- Correctness and contract safety: 30
- Reliability and operability: 25
- Security and compliance posture: 20
- Product and UX fitness: 15
- Documentation and plan hygiene: 10

## Scoring Rubric
- 90-100: Ready for production merge.
- 75-89: Acceptable with explicit follow-ups.
- 60-74: Significant risk; require remediation before merge.
- <60: Not merge-ready.

## Gate Criteria
- Contract safety
  - Proto/event changes are backward-compatible or explicitly migrated.
- Reliability
  - Relevant tests/checks executed.
  - Observability verification performed for impacted flows.
- Security
  - Authn/authz and data handling implications reviewed.
- Product
  - Acceptance criteria in linked spec met.
- Documentation
  - Plan/spec/architecture/reliability/security docs updated as required.

## Reporting Template
| Change | Score | Notes | Required Follow-ups |
|---|---:|---|---|
| <change-id> | <0-100> | <summary> | <actions> |
