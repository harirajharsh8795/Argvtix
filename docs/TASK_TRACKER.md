# Living Project Task Tracker (TASK_TRACKER.md)

**System:** Argvtix / ARGVTIX Production Launch Readiness  
**Status Key:** `BACKLOG` | `READY` | `IN_PROGRESS` | `BLOCKED` | `IN_REVIEW` | `DONE` | `CANCELLED`  
**Priority Key:** `P0` (Critical/Blocker) | `P1` (High) | `P2` (Medium) | `P3` (Low/Polish)  
**Last Synchronized:** 2026-10-27  

---

## 1. Documentation & Governance

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DOC-001** | Create Product Requirements Document | P1 | `DONE` | `docs/PRD.md` | Complete product overview, user journeys, functional and non-functional specs | Documentation Review | Document published and verified against repository functionality |
| **DOC-002** | Create Technical Architecture Document | P1 | `DONE` | `docs/ARCHITECTURE.md` | Full stack topology, data flows, database design, API design, infrastructure | Documentation Review | Published with Mermaid diagrams and stack justification |
| **DOC-003** | Create Design System Document | P2 | `DONE` | `docs/DESIGN_SYSTEM.md` | Surface tokens, color palette, typography scale, component rules, a11y standards | Visual Token Audit | Aligned with `ui/src/index.css` design tokens |
| **DOC-004** | Create Project Memory Document | P1 | `DONE` | `docs/PROJECT_MEMORY.md` | Durable state tracking, technical decisions, commands, implementation context | Documentation Review | Published with verified engineering decisions |
| **DOC-005** | Create Permanent Coding Rules | P0 | `DONE` | `docs/AGENTS.md` | Strict security invariants, API rules, database rules, change management | Rule Verification | Published as canonical standard for all agents |
| **DOC-006** | Create Living Task Tracker | P1 | `DONE` | `docs/TASK_TRACKER.md` | Structured living task table with priority, status, and verification | Tracker Audit | Initialized with complete launch readiness scope |

---

## 2. Database Optimization & Performance

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PERF-001** | Audit & Eliminate Watchdog N+1 Queries | P0 | `DONE` | `src/argvtix/watchdog/rules/*.py` | Replace entity loops with database-level SQL aggregations; reduce query count $> 90\%$ | Benchmark Suite (`bench/benchmark_performance.py`) | Queries dropped from 1,393 to 6 (99.57% reduction); latency dropped 31.2x (1,519ms -> 48.7ms) |
| **PERF-002** | Collapse Trace Stats Aggregation Queries | P1 | `DONE` | `src/argvtix/gateway/app.py` | Collapse 5 separate queries into 1 SQL statement using conditional sums | Unit & Benchmark Tests | 80% query reduction (5 -> 1); latency reduced from 9.48ms to 3.66ms |
| **PERF-003** | Create Reversible Index Migration | P1 | `DONE` | `alembic/versions/004_performance_indexes.py` | Establish 12 composite and status indexes across 9 models | Alembic Upgrade / Downgrade verification | Migration applied cleanly to schema |
| **PERF-004** | Configure Bounded Connection Pool | P0 | `DONE` | `src/argvtix/db/session.py` | Configurable pool size (15), max overflow (10), timeout (30s), pre-ping enabled | Code Review & Automated Pool Tests | Verified in `tests/test_performance_resilience.py` |

---

## 3. Intelligent Caching Architecture

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CACHE-001**| Multi-Tier Cache Engine Implementation | P0 | `DONE` | `src/argvtix/cache/manager.py` | In-memory LRU TTL bounded cache (10k items) with Redis distributed support | Unit Tests (`tests/test_performance_resilience.py`) | $O(1)$ operations, eviction, and TTL verified |
| **CACHE-002**| Resilient Transparent Fallback | P0 | `DONE` | `src/argvtix/cache/manager.py` | Transparent fallback to local memory if Redis is partitioned or restarting | Offline Redis Socket Test | Passed; zero 500 errors when Redis is disconnected |
| **CACHE-003**| Distributed Tool Gateway Idempotency | P1 | `DONE` | `src/argvtix/guard/gateway.py` | Store tool idempotency keys in shared cache with 24h TTL | Integration Test | Replaced local dict; enabled multi-replica scale |
| **CACHE-004**| Cache Invalidation on Mutations | P1 | `DONE` | `src/argvtix/gateway/app.py` | Invalidate `traces:*` on new trace ingestion via `delete_pattern` | Integration Test | Verified event-driven cache invalidation |
| **CACHE-005**| Cache Observability Endpoint | P2 | `DONE` | `src/argvtix/gateway/app.py` | Expose `GET /api/v1/cache/metrics` returning hits, misses, hit ratio | HTTP Endpoint Test | Returns JSON metrics with 98%+ hit ratio |

---

## 4. Realistic Load & Stress Testing

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **LOAD-001** | Build Asynchronous Load Testing Suite | P1 | `DONE` | `bench/load_test.py` | Realistic user journeys across 8 routes; Smoke, Load, Stress, Spike profiles | Asynchronous HTTP Suite Execution | Benchmark scripts committed to repository |
| **LOAD-002** | Execute Live Stress & Spike Benchmarks | P0 | `DONE` | `bench/load_test_results.json` | 0 server 5xx errors under 100 concurrent workers; p50 < 1.2s under spike | Automated Test Logs | 1,650 total requests executed with 0 server errors |

---

## 5. Containerization & Deployment Hardening

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEPL-001** | Multi-Stage Hardened Dockerfile | P1 | `DONE` | `Dockerfile` | Multi-stage build, unprivileged `appuser` (UID 10001), native healthcheck | Dockerfile Syntax & Layer Inspection | Image builder and runtime isolated |
| **DEPL-002** | Production Dockerignore Isolation | P1 | `DONE` | `.dockerignore` | Exclude `.git`, `.env*`, dev databases, and caches from image context | File Audit | Created and verified |
| **DEPL-003** | Upstream Load Balancing NGINX Config | P1 | `DONE` | `infra/nginx.conf` | `least_conn` upstream, retry on 5xx, WebSocket proxying, 1y asset caching | NGINX Configuration Review | Upstream cluster and proxy headers configured |
| **DEPL-004** | Multi-Replica Production Compose | P1 | `DONE` | `docker-compose.prod.yml` | 3 API replicas, standalone migration container, Redis, PostgreSQL | Compose Config Validation | Configured with resource quotas and health checks |

---

## 6. Security Hardening & Website Launch Readiness

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-001**  | Role-Based Authorization & Tenant Scoping | P0 | `DONE` | `src/argvtix/gateway/app.py` | Protected routes require valid JWT and appropriate role (`OPERATOR`, `ADMIN`) | Automated Auth Tests (`test_security/`) | Verified in test suite |
| **SEC-002**  | Rate Limiting on Sensitive Endpoints | P1 | `DONE` | `src/argvtix/gateway/app.py` | 5 req/min on contact form; 15 req/min on scans; HTTP 429 on breach | Load Test Verification | Verified in Load Profile (10 rate limits triggered on flood) |
| **SEC-003**  | PII Masking & DLP Filtering | P0 | `DONE` | `src/argvtix/security/` | Mask emails, credit cards, SSNs, and phone numbers in traces | Automated Tests (`test_security/test_week6.py`) | All PII regex filters passing |
| **SEC-004**  | Security Headers (CSP, HSTS, X-Frame) | P1 | `DONE` | `app.py`, `nginx.conf` | Inject strict security headers on all responses | Middleware & NGINX Config Test | Headers active on all routes |
| **SEC-005**  | Cloudflare Turnstile Verification | P1 | `DONE` | `src/argvtix/gateway/app.py` | Server-side verification of Turnstile token on contact form | Integration Test | Supports test mode and production secret key |
| **LAUNCH-001**| SEO Meta Tags & Social Previews | P2 | `DONE` | `ui/index.html`, `public/` | Unique titles, meta descriptions, Open Graph image (`og-preview.png`), favicon | HTML & Public Asset Inspection | Meta tags and preview images in place |
| **LAUNCH-002**| XML Sitemap & Robots.txt | P2 | `DONE` | `ui/public/sitemap.xml`, `robots.txt` | Valid sitemap with priority tags and clean robots.txt | Public File Verification | Configured for `https://argvtix.ai` |
| **LAUNCH-003**| Branded Custom Error Pages (404 / 500) | P2 | `DONE` | `ui/src/pages/NotFoundPage.tsx` | Informative 404 page with navigation return actions | React Route Test | Route `*` redirects to `NotFoundPage` |
| **LAUNCH-004**| Legal & Privacy Pages | P2 | `DONE` | `PrivacyPage.tsx`, `TermsPage.tsx` | Clear disclosure of cookies, data processing, and analytics | Page Route Inspection | `/privacy-policy` and `/terms` active |
| **LAUNCH-005**| Google Analytics Consent Gating | P2 | `DONE` | `ui/src/utils/analytics.ts` | Gated by user consent banner (`CookieConsent.tsx`) | Component Code Audit | Analytics respects privacy choice |
| **EXT-001**  | Production Cloud Redis Deployment | P1 | `BLOCKED`| Cloud Infrastructure | Dedicated managed Redis instance in AWS/GCP | Cloud Console | Awaiting production cloud infrastructure provisioning |
| **EXT-002**  | Production Cloudflare Turnstile Secret | P1 | `BLOCKED`| Cloudflare Dashboard | Set `CLOUDFLARE_TURNSTILE_SECRET_KEY` in production secrets | Environment Config | Ready for deployment with real domain keys |

---

## 7. Outcome Assurance, Benchmarking & Scout Black-Box Audits

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BENCH-001**| 60-Case Argvtix Bench Suite | P1 | `DONE` | `bench/runner.py`, `bench/cases/` | Evaluate 60 failure taxonomy cases across dev (40) and held-out (20) splits | CLI Benchmark Execution | Dev: 100% Acc/F1; Held-out: 95.0% Acc, 97.44% F1 |
| **DEMO-001** | Outcome Assurance Interactive Demo Runner | P1 | `DONE` | `run_demo.py` | 12-step lifecycle: Hinglish ticket ingestion, Action Guard ₹15k block, Claim-vs-State Verifier, 13ms Watchdog | CLI Execution & Evidence Export | Flawlessly executed; `bench/demo_evidence_packet.json` generated |
| **SCOUT-001**| Scout Black-Box Audit Execution & Case Study | P1 | `DONE` | `scripts/run_scout_audit.py`, `docs/case_studies/` | 12-category probe battery against ShopOps target, human sign-off gate, report & packet generation | Script Execution | Executive report & machine-readable evidence packet published |
| **OTEL-001** | OpenTelemetry (OTel) Exporter | P2 | `DONE` | `src/argvtix/trace/otel_export.py` | W3C TraceContext (`traceparent`), OTLP ResourceSpans, GenAI semantic conventions | Unit Tests & Export Verification | Standard W3C & OTLP JSON export verified |
| **SPEND-001**| LLM Token Spend Guard Controller | P1 | `DONE` | `src/argvtix/target_app/spend_guard.py` | Thread-safe daily and monthly USD token spend tracking with hard cap enforcement | Unit Tests (`test_week8.py`, `test_demo_and_scout.py`) | Enforces budget caps; blocks runaway agent loops |
| **TEST-001** | Comprehensive Regression Test Suite | P0 | `DONE` | `tests/test_demo_and_scout.py` | 100% test coverage for demo, Scout runner, OTel export, and spend guard | Pytest Suite Execution | 8/8 new tests passing; 328/328 total tests green |

---

## 8. Ten Reported Defects & Independent Verification Audit

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-001** | Canonical Product Nomenclature & Sidebar Labels | P1 | `DONE` | `ui/src/components/Sidebar.tsx` | Align labels: `/traces` -> 'Trace Explorer', `/watchdog` -> 'Data Watchdog', `/guard` -> 'Guardrails & Approvals' | Visual Inspection & Component Test | Labels unified across sidebar and routes |
| **DEF-002** | Swagger UI Availability & Trace Contract Alignment | P1 | `DONE` | `src/argvtix/gateway/app.py` | FastAPI `/docs` returns 200 in dev; `/api/v1/traces` returns both `traces` and `items` with `id` and `trace_id` | HTTP Schema Contract Verification | Both UI contract and SDK contract supported |
| **DEF-003** | Structured Logging & Real-Time Action Audit Logs | P1 | `DONE` | `src/argvtix/gateway/app.py` | Structured audit logging on Guard check, approvals, claim verification, and pass@k runs | Backend Log Audit | Request logging middleware and audit log calls added |
| **DEF-004** | Fix Profile Comparison Routes in Benchmark Page | P1 | `DONE` | `ui/src/pages/BenchmarkPage.tsx` | Remove hardcoded `http://localhost:8000` URLs; support relative routes | Network Audit | Verified relative endpoint calls |
| **DEF-005** | Request / FAQ 6-Item Responsive 2x3 Grid | P2 | `DONE` | `ui/src/pages/LandingPage.tsx` | Render questions 1-6 in 2x3 responsive card grid with Q1-Q6 badges and keyboard access | UI Rendering Audit | Grid layout with CSS transitions active |
| **DEF-006** | Trace Waterfall Execution Spans & Diffs | P1 | `DONE` | `ui/src/pages/TracesPage.tsx` | Loading a trace fetches detail via `api.getTraceDetail()` to render execution spans and state diffs | Component State Audit | Waterfall drawer renders chronological execution spans |
| **DEF-007** | Guardrails & Approvals Refresh & Auto-Auth | P1 | `DONE` | `GuardPage.tsx`, `client.ts` | Refresh button functional; auto-provision operator JWT to prevent 401 on approval actions | API Integration Test | Token provisioning and queue refresh verified |
| **DEF-008** | Claim Verifier Pass^k Metric Alignment | P1 | `DONE` | `app.py`, `EvalsPage.tsx` | Map `pass_hat_k` and `pass_pow_k` compatibility aliases; remove hardcoded 96.8 fallback | Metric Audit | Dynamic pass@k values rendered accurately |
| **DEF-009** | Grounding Verification & Snapshot Error Handling | P0 | `DONE` | `app.py`, `EvalsPage.tsx`, `extractor.py` | Accept `{ response_text, state_snapshot }`; handle comma amounts (₹1,200); remove fake fallback | E2E Audit | Real grounding and violation details rendered |
| **DEF-010** | Website-Wide Micro-Animations & A11y | P2 | `DONE` | `ui/src/index.css` | Smooth interactive transitions with `@media (prefers-reduced-motion)` support | CSS Token & A11y Audit | Full animation support verified |
| **AUDIT-001**| Independent Verification Suite | P0 | `DONE` | `tests/test_independent_audit.py` | End-to-end evaluation of Journeys A-H, 25 Misbehavior Scenarios, velocity caps, state preconditions | Pytest Execution | 42/42 tests passing green |

---

## 9. Release Staging & Production Readiness Hardening

| Task ID | Task Title | Priority | Status | Files / Modules | Acceptance Criteria | Verification Method | Latest Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PROD-001** | Atomic Database-Level Refund Idempotency | P0 | `DONE` | `models.py`, `shop_tools.py`, `gateway.py` | Unique `idempotency_key` constraint on `Refunds`; concurrent workers cannot commit duplicate refunds | Concurrency Test (`test_atomic_idempotency_concurrent_refunds`) | Zero duplicate commits under multi-threaded load |
| **PROD-002** | Production Startup Configuration Validation | P0 | `DONE` | `src/argvtix/gateway/app.py` | Startup refuses to run on SQLite if `ENVIRONMENT=production`; enforces high-entropy JWT key | Startup LifeCycle Test (`test_production_rejects_sqlite_database_url`) | Explicit `RuntimeError` raised on bad prod config |
| **PROD-003** | Fail-Closed Turnstile Form Protection in Prod | P1 | `DONE` | `src/argvtix/gateway/app.py` | In production, contact form fails closed (HTTP 400) if Turnstile secret or token is missing | Automated Test (`test_turnstile_fail_closed_in_production`) | Prevents unverified bypass in production |
| **PROD-004** | Comprehensive Operations Runbook & Migration Guide | P1 | `DONE` | `docs/RUNBOOK.md` | Complete runbook with setup, migrations, backups, health checks, and rollback | Documentation Review | Published as canonical operations guide |
| **PROD-005** | Live Safe Database Backup & Restore Verification | P0 | `DONE` | `argvtix.db` | Online hot backup, restore to target, integrity check, row count reconciliation | Script Verification | 14 tables verified; `PRAGMA integrity_check == ok` |
| **PROD-006** | Production Readiness Test Suite Expansion | P0 | `DONE` | `tests/test_production_readiness.py` | 12 independent production readiness & security tests | Pytest Execution | 382/382 total tests passing green (100%) |
| **STAG-001** | Staging Verification & 10 User Journeys | P0 | `DONE` | `tests/test_staging_scenarios.py` | 10 end-to-end scenarios covering low/high refunds, concurrency, IDOR, verifier, spans, restarts | Pytest Execution | 10/10 scenarios passed green |
| **STAG-002** | Docker Compose & NGINX DNS Alignment | P1 | `DONE` | `infra/nginx.conf`, `docker-compose.prod.yml` | Align upstream DNS names and add container network aliases (`api`, `argvtix-api`) | Config Audit | Zero DNS resolution errors on cluster launch |
| **PROD-007** | Live Multi-Process OS Concurrency Verification | P0 | `DONE` | `tests/test_multiprocess_concurrency.py` | Spawns multiple independent OS Python processes with separate heaps/interpreters against SQLite WAL | Pytest Subprocess Execution | 100% atomic idempotency; exactly 1 row committed across processes |
| **BROWSER-001**| Real Browser Acceptance Test Suite (Playwright) | P0 | `DONE` | `tests/test_browser_acceptance.py` | 10 complete Playwright Chromium user journeys: login, nav, approvals, rejection, IDOR, claims, traces | Playwright Execution | 10/10 journeys passing in 11.10s |
| **LOAD-003** | Live HTTP Load Benchmark & Performance Verification | P1 | `DONE` | `bench/load_test.py` | Live load profile execution against ASGI server; measures throughput, p50, p95, p99 | Benchmark Execution | 234.42 req/sec; p50=14.23ms; p95=80.90ms; 0 server 5xx errors |
| **TEST-003** | Full Regression Test Suite Expansion to 403 Tests | P0 | `DONE` | `tests/` | Comprehensive test coverage across all subsystems | Pytest Execution | 403/403 passed green in 33.49s (100% pass rate) |
