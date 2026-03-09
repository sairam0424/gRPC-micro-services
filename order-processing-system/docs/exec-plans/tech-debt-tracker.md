# Tech Debt Tracker

Track technical debt that impacts reliability, security, scalability, or delivery speed.

## Scoring Model
- Severity: `S0` (critical) to `S3` (low)
- SLO Risk: `High`, `Medium`, `Low`
- Priority is determined by Severity + SLO Risk + Blast Radius.

## Debt Register

| ID | Area | Item | Severity | Impact | Owner | Status | SLO Risk | Target Resolution | Notes |
|---|---|---|---|---|---|---|---|---|---|
| TD-001 | Documentation | Legacy and new architecture docs can diverge without explicit sync routine | S2 | Contributor confusion and slower incident response | Platform Docs | Open | Medium | 2026-04-15 | Add monthly architecture consistency review |
| TD-002 | Contracts | Some generated gRPC comments indicate missing proto method docs | S3 | Slower onboarding and API ambiguity | API Contracts | Open | Low | 2026-05-01 | Add proto doc completeness check in future CI pass |
| TD-003 | Observability | Metric naming and dashboard ownership are not centrally cataloged | S2 | Delayed diagnostics during outages | SRE/Platform | Open | Medium | 2026-04-30 | Create metric catalog under reliability docs |

## Update Rules
- Add an entry when debt is intentionally accepted during implementation.
- Update status at least once per execution-plan cycle.
- Close only after validation evidence is linked in a completion report.
