# FRONTEND

Frontend behavior must reflect backend truth and service constraints.

## Current Stack
- Next.js app router under `web-client/src/app`.
- Component system: UI primitives under `web-client/src/components/ui`.
- Data flow: REST endpoints + SSE (`/api/orders/events`) via gateway/proxy.

## Frontend Architecture Rules
- Treat gateway endpoints as canonical client interface.
- Ensure loading/error/empty states for all networked views.
- Preserve stable UX during transient backend failures (retries/reconnect hints).
- Never mask terminal order states; surface clear failure reasons when available.

## UI/UX Expectations for Core Flows
- Auth: signup/login feedback must be explicit and actionable.
- Order create: immediate submission feedback and transition visibility.
- Live updates: SSE reconnection behavior must avoid confusing duplicates.
- Search and dashboard views: support degraded mode when secondary systems are unavailable.

## Quality Gates
- No broken route-level navigation.
- No uncaught client errors on common order flow paths.
- Explicit state transitions visible in UI.

## References
- [Product Spec: New User Onboarding](./product-specs/new-user-onboarding.md)
- [Frontend Integration](./frontend_integration.md)
- [Reliability](./RELIABILITY.md)
- [Security](./SECURITY.md)
