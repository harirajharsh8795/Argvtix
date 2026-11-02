# Project Memory & Engineering State

**Project:** Argvtix / ARGVTIX (Enterprise AI Reliability & Protection Platform)  
**Current Milestone:** Production Release Candidate Hardening & Launch Readiness  
**Target Environment:** Containerized Cloud Linux (Docker / Kubernetes) & Local Development  
**Document Purpose:** Durable AI engineering context, verified state, and technical decision log.  
**Last Updated:** 2026-10-27  

---

## 1. Verified Project State

### 1.1 What the Platform Does
Argvtix (ARGVTIX) intercepts, observes, and validates actions taken by autonomous AI agents. It provides pre-action runtime guardrails (`ActionGuard`), silent data corruption detection (`WatchdogEngine`), distributed execution tracing (`TraceStore`), prompt injection & DLP defenses (`Security`), LLM evaluation regression gates (`CI Gate`), and an enterprise operator web console (`React + Vite`).

### 1.2 Current Architecture Status
- **Backend:** FastAPI ASGI application running under Python 3.12 with async route handlers, connection pooling, and JWT authorization.
- **Frontend:** React 18 SPA built with Vite 8 and TypeScript, styled with zero-runtime Vanilla CSS variables.
- **Database:** SQLAlchemy ORM with PostgreSQL in production and SQLite in local development. 12 composite & status indexes applied via Alembic migration `004_performance_indexes.py`.
- **Cache Engine:** Multi-tier `CacheManager` featuring process-local bounded `InMemoryLRUTTLCache` (10,000 items) and distributed `RedisCache` (Redis 7.2) with seamless transparent fallback.
- **Deployment:** Multi-stage hardened `Dockerfile` running unprivileged `appuser`, upstream `least_conn` NGINX reverse proxy (`infra/nginx.conf`), and multi-replica `docker-compose.prod.yml`.

---

## 2. Important Technical Decisions Log

| Decision ID | Decision Made | Rationale | Alternatives Evaluated & Rejected |
| :--- | :--- | :--- | :--- |
| **DEC-001** | Bounded in-memory LRU+TTL cache with Redis fallback | Guarantees zero downtime: if Redis fails or restarts, API degrades safely to memory cache without throwing 500 errors. | Direct Redis-only dependency (failed due to hard external dependency risk). |
| **DEC-002** | Database-level SQL aggregations for Watchdog rules | Eliminated N+1 query loops. Watchdog query volume reduced by 99.57% (1,393 queries down to 6 queries). | Python-side entity iterations (caused CPU memory spikes and 1.5s+ latency). |
| **DEC-003** | Collapsed trace stats query into 1 SQL statement | Combined total count, error count, avg latency, and sum of cost using conditional SQL `sum(case(...))`. | 5 sequential round-trip queries (caused latency under dashboard polling). |
| **DEC-004** | Distributed idempotency keys via `cache_manager` | Enables stateless horizontal scaling across multiple API replicas without shared memory leaks. | Process-local Python dictionary in `ToolGateway` (broke across multi-replica pods). |
| **DEC-005** | Standalone migration container in Docker Compose | Avoids race conditions where multiple API pods attempt to run `alembic upgrade head` simultaneously. | Running migrations in API container startup scripts. |
| **DEC-006** | Dual-contract support for `/api/v1/traces` | Return both `traces` and `items`, each with both `id` and `trace_id` properties, ensuring complete compatibility between UI clients and SDK clients without breaking changes. | Breaking existing SDK client or forcing frontend rewrite. |
| **DEC-007** | Comma-tolerant multilingual amount extraction | Regex updated to handle `[0-9,]+(?:\.[0-9]+)?` with `.replace(',', '')` so amounts like `₹1,200` are correctly evaluated as 1200.0 rather than truncated to 1.0. | Stripping non-alphanumeric characters globally (broke punctuation and decimals). |
| **DEC-008** | Multi-factor Action Guard policy engine | Pre-action validation enforcing negative amount rejection, IDOR customer ownership verification, order cancellable state invariants, and customer hourly velocity caps. | Relying on post-action database rollbacks (leaves agent in undefined state). |

---

## 3. Implementation Context & Commands

### 3.1 Core Commands
- **Run Backend Locally:**
  ```bash
  python -m uvicorn argvtix.gateway.app:app --host 127.0.0.1 --port 8000
  ```
- **Run Frontend Locally:**
  ```bash
  cd ui && npm run dev
  ```
- **Execute Automated Test Suite:**
  ```bash
  python -m pytest tests/ -q
  ```
- **Execute Performance Resilience Tests:**
  ```bash
  python -m pytest tests/test_performance_resilience.py
  ```
- **Execute Asynchronous Load Testing:**
  ```bash
  python -u bench/load_test.py --url http://127.0.0.1:8000 --profile all
  ```
- **Build Frontend Production Bundle:**
  ```bash
  cd ui && npm run build
  ```

### 3.2 Key Directories
- `src/argvtix/cache/`: Multi-tier caching engine (`CacheManager`, `InMemoryLRUTTLCache`, `RedisCache`).
- `src/argvtix/guard/`: Pre-action safety guard (`ActionGuard`, `ToolGateway`, `ApprovalQueue`).
- `src/argvtix/watchdog/`: Data consistency rules (`rules/order_total_mismatch.py`, `duplicate_refund.py`, etc.).
- `src/argvtix/gateway/`: FastAPI routers, CORS, security headers, rate limiting, and WebSockets.
- `ui/src/`: React pages (`LandingPage.tsx`, `OverviewPage.tsx`, `TracesPage.tsx`, `GuardPage.tsx`, `ContactPage.tsx`).

---

## 4. Current Session Summary

### 4.1 Modifications & Accomplishments
1. **Database Query Optimization:**
   - Identified 1,393-query cascade in Watchdog scanning.
   - Refactored 6 watchdog rules to database-level SQL aggregations and joins.
   - Verified 31.2x latency reduction (1,519 ms -> 48.7 ms).
   - Created Alembic migration `004_performance_indexes.py` establishing 12 composite indexes.
2. **Intelligent Caching Implementation:**
   - Implemented `InMemoryLRUTTLCache` with LRU eviction and TTL expiration.
   - Implemented `RedisCache` with resilient fallback.
   - Added `traces:stats` caching (5s TTL) with event-driven invalidation on trace ingestion.
   - Added cache observability endpoint `GET /api/v1/cache/metrics`.
3. **Realistic Load Testing:**
   - Built and executed `bench/load_test.py` across Smoke, Load, Stress, and Spike profiles.
   - Verified 0 server crashes / 5xx errors across 1,650 test requests up to 100 concurrent workers.
   - Observed 98.62% cache hit ratio under traffic.
4. **Production Hardening:**
   - Created multi-stage hardened `Dockerfile` with non-root user `appuser` (UID 10001) and health checks.
   - Created `.dockerignore` for credential and database isolation.
   - Updated `infra/nginx.conf` with `least_conn` upstream load balancing and WebSocket streaming.
   - Configured `docker-compose.prod.yml` with Redis, PostgreSQL, and 3 API replicas.
5. **Quality Assurance:**
   - Added `tests/test_performance_resilience.py` (5/5 tests passing).
   - Full test suite verified green: **320 / 320 tests passing**.

### 4.2 Outstanding External Requirements
- Cloud Redis deployment URL (`REDIS_URL`) in production environment.
- Cloudflare Turnstile production secret key (`CLOUDFLARE_TURNSTILE_SECRET_KEY`) for live lead form CAPTCHA.
- Production PostgreSQL connection string (`DATABASE_URL`).
