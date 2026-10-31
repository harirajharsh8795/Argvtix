# Permanent Agent Coding & Security Rules (AGENTS.md)

**Scope:** All AI coding agents, automated workflows, and pair-programming sessions in the `earp` repository.  
**Governing Standard:** Defense-in-Depth, Zero-Trust, Empirical Verification.  
**Last Updated:** 2026-10-27  

---

## 1. Repository Rules

1. **Strict Stack Preservation:** Follow the existing technology stack (FastAPI, Python 3.12, SQLAlchemy 2.0, Alembic, React 18, TypeScript, Vite, Vanilla CSS). Never introduce external frameworks, alternate database engines, or conflicting CSS libraries without explicit user instruction.
2. **Respect Directory Organization:** Place code exclusively in its established module (`src/earp/guard`, `src/earp/watchdog`, `src/earp/gateway`, `ui/src/pages`, `ui/src/components`, `tests/`).
3. **Reuse Established Patterns:** Never reinvent existing utilities. Use `cache_manager` for caching, `get_db` for database sessions, `limiter` for rate limiting, and CSS variables from `index.css` for styling.
4. **No Destructive Operations:** Never delete user databases, reset migration histories, or drop tables in existing schemas.

---

## 2. Security Invariants

1. **Server-Side Validation Mandatory:** Never rely on client-side validation alone. Every untrusted payload must be validated using Pydantic models on the server.
2. **Server-Enforced Authorization:** Enforce authentication and role permissions (`require_role(Role.OPERATOR)`) on the server. Never rely on frontend route guards or hidden UI elements.
3. **Parameterized Queries Only:** Execute database operations exclusively through SQLAlchemy ORM or parameterized `text()` queries. Never concatenate untrusted strings into SQL.
4. **Zero Hardcoded Secrets:** Never hardcode credentials, API keys, JWT secrets, or infrastructure passwords in source files, Dockerfiles, or tests. Always retrieve from environment variables.
5. **No Secret Leaks in Responses or Logs:** Mask all credentials, tokens, and PII before logging. Never expose internal stack traces or database connection strings to API clients.
6. **Defense Against IDOR:** When querying or modifying entities (orders, approvals, traces), verify that the requesting tenant or user owns the resource (`project_id` scoping).
7. **Never Bypass Security to Pass Tests:** Never comment out authentication checks, rate limits, or validation logic to make a test pass. Fix the test fixture instead.

---

## 3. API & Data Contract Rules

1. **Preserve API Contracts:** Maintain backwards compatibility for existing JSON schemas, route paths, and HTTP methods.
2. **Accurate HTTP Status Codes:**
   - `200 OK`: Successful retrieval or execution.
   - `201 Created`: Resource successfully persisted.
   - `400 Bad Request`: Malformed payload or validation error.
   - `401 Unauthorized`: Missing or invalid JWT token.
   - `403 Forbidden`: Authenticated user lacks required role.
   - `404 Not Found`: Entity does not exist.
   - `422 Unprocessable Entity`: Schema mismatch.
   - `429 Too Many Requests`: Rate limit exceeded.
3. **Mandatory Pagination:** Endpoints returning unbounded lists (traces, audit findings, approvals) must provide `limit` and `offset` query parameters.
4. **Idempotency in Mutations:** State-changing operations (tool executions, approvals) must support idempotency keys to prevent duplicate execution during network retries.

---

## 4. Database Optimization & Migration Rules

1. **Zero N+1 Cascades:** Never iterate through database records in Python while firing relationship queries. Use SQL `join()`, `outerjoin()`, or `subquery()` aggregations.
2. **Measurable Indexing:** Add indexes only where query patterns or benchmarks demonstrate a bottleneck. Always specify meaningful index names (`ix_{table}_{columns}`).
3. **Reversible Migrations:** Every Alembic migration file must include both `upgrade()` and `downgrade()` functions.
4. **Online Schema Safety:** Ensure schema modifications avoid long-lived exclusive table locks on production tables.

---

## 5. Testing & Quality Invariants

1. **Mandatory Test Execution:** Execute relevant tests after every substantial code change.
2. **Zero False Positives:** Never mark a test as passed without executing it and observing the exit code.
3. **Regression Tests for Bugs:** Every fixed defect or performance bottleneck must be paired with an automated regression test.
4. **Full Test Suite Integrity:** The full test suite (`python -m pytest tests/ -q`) must remain 100% green before declaring any milestone complete.

---

## 6. Frontend & UI Conventions

1. **Follow `DESIGN_SYSTEM.md`:** Use existing CSS variables (`--bg-surface`, `--text-primary`, `--emerald`, `--cyan`, `--radius-md`).
2. **Accessible Interaction:** Maintain visible focus outlines (`--cyan`), semantic HTML, and proper keyboard navigability (`Enter` / `Space`).
3. **Four Universal UI States:** Every dynamic component must gracefully handle:
   - Loading State (spinner / skeleton pulse).
   - Empty State (informative icon + descriptive label + CTA).
   - Success State (toast notification or badge update).
   - Error State (inline banner with non-technical guidance).
4. **Zero Layout Shifts:** Reserve dimensions for charts, images, and tables to avoid Cumulative Layout Shift (CLS).

---

## 7. Change Management Workflow

Before executing any substantial change:
1. **Inspect:** Examine existing files and read relevant documentation.
2. **Assess Risk:** Identify potential regressions in API contracts, database schemas, or UI behavior.
3. **Plan:** Formulate the smallest sufficient, surgical change.
4. **Implement:** Apply code edits cleanly.
5. **Verify:** Run automated unit/integration tests and compile the frontend.
6. **Document:** Synchronize `PROJECT_MEMORY.md` and `TASK_TRACKER.md`.
