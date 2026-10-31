# Product Requirements Document (PRD)

**Product Name:** Proofline / EARP (Enterprise AI Reliability & Protection Platform)  
**Version:** 1.0.0 (Production Release Candidate)  
**Status:** Approved for Production Hardening  
**Document Owner:** Principal Software Engineer & Release Manager  
**Last Updated:** 2026-10-27  

---

## 1. Product Overview

### 1.1 Purpose
Proofline (EARP) is an enterprise-grade AI reliability, governance, and runtime protection platform designed to wrap around autonomous agentic workflows (e.g., ShopOps AI agents, automated support bots, backend tool execution pipelines). It monitors agent behavior, enforces pre-action safety guardrails, detects silent data corruption, masks sensitive PII, and gates deployments through automated evaluation suites.

### 1.2 Problem Statement
Enterprises deploying Large Language Model (LLM) agents into production face critical operational risks:
1. **Uncontrolled Tool Execution:** Agents hallucinate parameters or invoke high-impact tools (e.g., issuing refunds, deleting inventory, modifying user permissions) without policy validation.
2. **Silent Data Integrity Drift:** Inconsistent transactions, orphaned records, or unbalanced ledger entries occur silently in underlying databases.
3. **Data Leakage & PII Exposure:** Sensitive customer data (emails, credit card numbers, phone numbers, API keys) leaks through LLM context windows or agent logs.
4. **Lack of Deterministic Observability:** Difficulty reproducing agent regressions or understanding why an agent failed a multi-turn conversation.

### 1.3 Target Users & Personas
- **Chief Information Security Officers (CISOs) & Compliance Officers:** Require verifiable audit trails, PII masking, DLP enforcement, and tamper-proof approval logs.
- **Head of AI / Lead AI Engineers:** Require full-lifecycle tracing, prompt/response inspection, token cost accounting, and LLM evaluation benchmarks.
- **DevOps & Site Reliability Engineers (SREs):** Require sub-millisecond policy evaluation, high throughput, bounded memory consumption, and horizontal scalability.
- **Human Operations Staff (Operators):** Require an intuitive queue to inspect and approve or reject high-risk tool actions flagged by the runtime guard.

### 1.4 Primary Value Proposition
- **Pre-Action Zero-Trust Guardrails:** Blocks or gates risky actions *before* execution rather than merely alerting post-facto.
- **Automated Data Integrity Watchdog:** Scans database tables for anomalies with sub-50ms optimized SQL aggregations.
- **Enterprise-Grade Observability:** Complete distributed tracing with sub-millisecond cached dashboard stats and real-time WebSocket feeds.

---

## 2. Features & Functional Specifications

### 2.1 Feature Matrix

| Feature | Category | Status | Description |
| :--- | :--- | :--- | :--- |
| **Action Guard Engine** | Runtime Safety | Verified | Pre-execution policy engine evaluating tool parameters, financial limits, and business invariants. |
| **Human Approval Queue** | Governance | Verified | Real-time queue for actions requiring operator intervention (e.g., refunds > ₹10,000). |
| **Distributed Trace Store** | Observability | Verified | Persistent capture of prompts, model outputs, tool calls, costs, and latencies. |
| **Silent Data Watchdog** | Integrity | Verified | 6 SQL-optimized rules checking for orphan payments, duplicate refunds, ledger drift, and inventory mismatch. |
| **Security & DLP Suite** | Security | Verified | Regex-based PII masking, DLP filtering, and automated red-team prompt injection detection. |
| **Benchmark & Eval Gate** | Quality | Verified | Pass@k evaluation harness and CI gate to block regressions before deployment. |
| **Multi-Tier Cache Layer** | Performance | Verified | Process-local LRU+TTL cache with Redis distributed support and graceful degradation. |
| **Public Enterprise Portal** | Marketing / UX | Verified | Responsive marketing website, product demos, interactive ROI calculator, and lead capture form. |

### 2.2 Core User Journeys

#### Journey 1: Agent Tool Execution with Policy Interception
1. AI Agent proposes a tool call (e.g., `issue_refund(order_id="ord_1042", amount=15000.0)`).
2. Agent calls `POST /api/v1/guard/check`.
3. Guard evaluates policy: `amount >= 10000.0` triggers `ASK_HUMAN` policy rule (Max autonomous refund cap = ₹10,000.00; amounts meeting or exceeding threshold require human supervisor approval).
4. Action proposal is recorded into the `approval_queue` table with an idempotency key.
5. Guard returns `decision="ASK_HUMAN"`, `requires_human_approval=true`.
6. Operator reviews the approval request in the Web Console and clicks "Approve".
7. WebSocket event broadcasts the approval state change; agent completes the tool execution.

#### Journey 2: Automated Silent Data Integrity Scan
1. Watchdog engine runs scheduled or on-demand scan via `POST /api/v1/watchdog/scan`.
2. Engine executes 6 collapsed SQL queries across orders, payments, refunds, and ledger tables.
3. Discrepancies are flagged as `WatchdogFindingRecord` items (e.g., duplicate refund on order).
4. Anomalies appear in the Watchdog Console with severity badges and suggested remediation actions.

#### Journey 3: Enterprise Contact & Lead Ingestion
1. Enterprise visitor visits `https://proofline.ai/contact`.
2. Fills out lead form with Name, Email, Company, and Use Case.
3. Frontend validates format; submits to `POST /api/v1/contact`.
4. Rate limiter (`slowapi`) enforces 5 requests/minute threshold against automated spam.
5. Server generates unique submission ID and redirects to `/thank-you`.

---

## 3. Non-Functional Requirements

### 3.1 Performance & Scalability
- **API Latency:** $p50 < 80\text{ ms}$, $p95 < 350\text{ ms}$ under steady-state production load (20 concurrent workers).
- **Cache Hit Ratio:** $> 95\%$ on frequently polled endpoints (`/api/v1/traces/stats`).
- **Throughput:** Baseline $> 50\text{ req/sec}$ per API replica.
- **Database Connection Pool:** Bounded pool size ($15$ connections per replica, max overflow $10$, timeout $30\text{s}$, pre-ping enabled).

### 3.2 Security & Compliance
- **Authentication:** Stateless HMAC-SHA256 JWT tokens with role-based access control (`admin`, `operator`, `viewer`).
- **Data Protection:** No plaintext passwords; passwords hashed using bcrypt with salt work factor $\ge 12$.
- **Network Hardening:** Strict Content Security Policy (CSP), HTTP Strict Transport Security (HSTS), X-Content-Type-Options: nosniff, X-Frame-Options: DENY.
- **Input Sanitization:** Parameterized ORM queries across all endpoints; zero raw SQL string concatenation.

### 3.3 Reliability & High Availability
- **Graceful Cache Failure:** If Redis is partitioned or restarted, API operations must degrade safely to in-memory caching without throwing 500 errors.
- **Stateless Replicas:** API containers maintain no process-exclusive session state, allowing NGINX to distribute traffic with `least_conn` or round-robin algorithms.
- **Signal Handling:** Docker containers handle `SIGTERM` with 30s grace period for in-flight request completion.

### 3.4 Accessibility (a11y)
- WCAG 2.1 Level AA compliance.
- Visual focus indicators on all interactive inputs and buttons.
- Semantic HTML tags (`<main>`, `<nav>`, `<header>`, `<footer>`, `<section>`).
- Image alternative text (`alt`) configured for all illustrations and logos.

---

## 4. Scope & Boundaries

### 4.1 In-Scope (Release 1.0)
- Core observability, Action Guard, Watchdog, Security Red-Teaming, and Eval engines.
- Frontend web application with complete marketing landing page, documentation, and console dashboards.
- Reversible Alembic database migrations and composite indexing.
- Multi-stage Docker containerization and NGINX load balancer configuration.
- Comprehensive automated test suite (320 tests).

### 4.2 Out-of-Scope (Future Milestones)
- Real-money payment gateway settlement (mocked / test-mode idempotent ledger verified; production Stripe/Razorpay requires customer merchant credentials).
- SAML / Okta SSO integration (scheduled for v1.1).
- Multi-region active-active database replication.

---

## 5. Acceptance Criteria

1. **Security:** Zero high/critical vulnerabilities in dependencies; all protected endpoints reject unauthenticated or under-privileged requests with HTTP 401/403.
2. **Performance:** Full watchdog scan over 1,000+ business entities must execute in $< 100\text{ ms}$.
3. **Resilience:** Load testing up to 100 concurrent workers must yield $0.00\%$ HTTP 5xx server errors.
4. **Data Consistency:** Zero N+1 query cascades in core database operations.
5. **Quality Assurance:** 100% pass rate across the full pytest suite.
