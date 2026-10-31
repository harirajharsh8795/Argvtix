# ADR-008: JWT Authentication, Multi-Tenant RBAC, and Project Isolation

## Status
Accepted (Blueprint Correction Applied)

## Context
Initial prototypes operated with open CORS (`allow_origins=["*"]`) and unauthenticated endpoints. In enterprise multi-tenant deployments, unauthenticated access permits arbitrary users to inspect PII, trigger expensive watchdog scans, or alter approval decisions across tenants.

## Decision
We implemented a multi-tenant Role-Based Access Control (RBAC) model:
1. **Roles:**
   - `OWNER`: Full administrative control, project management, and user provisioning.
   - `ENGINEER`: Read/write access, can run eval benchmarks, watchdog scans, and trigger replays.
   - `REVIEWER`: Read access + authority to approve/reject pending HITL approval queue items.
   - `VIEWER`: Read-only access to metrics, dashboards, and reports.
2. **Project-Level Scoping:** Every trace, finding, and approval record includes a `project_id` column. Queries filter strictly by the `project_id` extracted from the verified JWT payload.
3. **Environment Gate:** Gated by `PROOFLINE_AUTH_ENABLED` (defaults to false in dev mode for friction-free local development; strictly enforced in production).

## Consequences
- **Positive:** Multi-tenant isolation, enterprise compliance, and audit trail security.
- **Trade-off:** Developers must pass tokens or use the dev token helper when auth is enabled.
