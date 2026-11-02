# Phase 1: Architecture & Performance Baseline Audit Report

**Platform:** ARGVTIX (Enterprise AI Reliability Platform) / Argvtix  
**Auditor:** Principal Backend Performance Engineer & SRE  
**Date:** October 27, 2026  
**Environment:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite (Local Dev) / PostgreSQL (Prod), Vite 8 + React 19 Frontend  

---

## 1. System Architecture Overview

```
                      ┌──────────────────────────────────────────────┐
                      │              Client Browser / SPA            │
                      └──────────────────────┬───────────────────────┘
                                             │ HTTP / WebSocket
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │    Reverse Proxy / Load Balancer (Nginx)     │
                      │   - Gzip Compression, Security Headers       │
                      │   - Static Asset Serving (/ui/dist)          │
                      └──────────────────────┬───────────────────────┘
                                             │ Reverse Proxy (:8000)
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │      FastAPI Gateway Control Plane           │
                      │   - Rate Limiter (SlowAPI)                   │
                      │   - Trace Ingestion & Observability          │
                      │   - Action Guard Pre-Execution Interceptor   │
                      │   - Watchdog Integrity Engine                │
                      │   - Claim Verifier & Regression Runner       │
                      └──────────────────────┬───────────────────────┘
                                             │ Connection Pool
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │    Relational Store (PostgreSQL / SQLite)    │
                      │   - 8 ShopOps Domain Tables                  │
                      │   - 3 Platform Observability Tables          │
                      └──────────────────────────────────────────────┘
```

---

## 2. Empirically Measured Baseline Performance

Measured across a realistic benchmark dataset (200 Customers, 800 Orders, 2,400 Order Items, 800 Payments, 200 Refunds, 1,000 Ledger Entries, 1,000 Traces, 3,000 Trace Steps):

| Operation / Endpoint | Baseline Latency (P50/Avg) | Database Queries Executed | Bottleneck Classification |
|---|---|---|---|
| **Watchdog Integrity Scan** (`POST /api/v1/watchdog/scan`) | **1,519.0 ms** | **1,393 queries** | **CRITICAL: N+1 Query Explosion** |
| **Trace Stats Aggregation** (`GET /api/v1/traces/stats`) | **9.48 ms** | **5 queries** | **HIGH: Redundant Table Scans** |
| **Trace Filter Query** (`GET /api/v1/traces?workflow=...`) | **6.19 ms** | **2 queries** | **MEDIUM: Missing Composite Indexes** |
| **Action Guard Check** (`POST /api/v1/guard/check`) | **4.40 ms** | **3 queries** | **MEDIUM: Unindexed Status Lookups** |
| **Watchdog Findings Filter** (`GET /api/v1/watchdog/findings`) | **5.73 ms** | **2 queries** | **MEDIUM: Missing Composite Index** |

---

## 3. Top Identified Performance Bottlenecks

### Bottleneck 1: N+1 Query Loop in Watchdog Rules (Critical)
- **`OrderTotalMismatchRule` (`order_total_mismatch.py:32-34`):**
  Iterates over every order and calls `order.items`, firing 800 individual `SELECT * FROM order_items WHERE order_id = ?` queries.
- **`InventoryDiscrepancyRule` (`inventory_discrepancy.py:40-42`):**
  Iterates over completed orders and checks `len(order.items)`, triggering another 400+ individual queries.
- **`LedgerBalanceRule` (`ledger_balance.py:36-37`):**
  Iterates over every customer and fires `db.query(LedgerEntry).filter(LedgerEntry.customer_id == cust.id).all()`, generating 200 queries.
- **`RefundExceedsPaymentRule` & `DuplicateRefundRule`:**
  Loads all records across entire tables into Python heap memory and aggregates via `defaultdict(float)`. Under a production dataset of 1M rows, this causes fatal Out-Of-Memory (OOM) crashes.

### Bottleneck 2: Missing Composite & Status Indexes (High)
- `orders.status`, `payments.status`, `refunds.status`, and `support_tickets.status` are completely unindexed.
- `TraceRecord` lacks composite indexes on `(workflow_type, created_at)` and `(status, created_at)`.
- `WatchdogFindingRecord` lacks composite indexes on `(resolved, detected_at)` and `(severity, detected_at)`.
- `TraceStepRecord` lacks composite index on `(trace_id, step_index)`.

### Bottleneck 3: 5 Separate Scans for Trace Stats Aggregation (Medium)
- `get_trace_stats()` executes 5 distinct `SELECT COUNT(...)`, `SELECT AVG(...)`, and `SELECT SUM(...)` statements against `traces` sequentially instead of a single multi-column aggregation.

### Bottleneck 4: Zero Caching Layer on Read-Heavy Polled Endpoints (High)
- The frontend dashboard polls `/api/v1/traces/stats` and `/api/v1/spend/summary` every 10 seconds.
- Currently, 100% of these calls execute live SQL queries against the database without in-memory or Redis caching.
- `ToolGateway` uses an in-memory dictionary for idempotency (`self._idempotency_cache`), which cannot scale horizontally across multi-replica or multi-worker deployments.

### Bottleneck 5: Unbounded Connection Pool & Missing Reverse Proxy Pooling (High)
- Default SQLAlchemy pool size is 5 with no explicit max overflow or pool recycling.
- Nginx in `infra/nginx.conf` points to a single backend container `http://argvtix-api:8000` with no upstream round-robin load balancer, no proxy timeouts, and no WebSocket support for real-time trace events.

---

## 4. Prioritized Engineering Remediation Plan

1. **Phase 2 (Database Optimization):**
   - Add composite indexes to `models.py` and create safe Alembic migration `004_performance_indexes.py`.
   - Refactor Watchdog rules to use SQL-level aggregations (`GROUP BY`, `SUM`, `joinedload`), eliminating all N+1 queries.
   - Collapse `get_trace_stats` from 5 queries into 1 SQL aggregation.
2. **Phase 3 (Intelligent Caching):**
   - Implement an extensible caching abstraction (`CacheManager`) supporting process-local TTL cache and distributed Redis cache.
   - Cache expensive dashboard aggregations (`stats`, `spend summary`, `findings count`) with write-through / event-driven invalidation upon trace ingestion and watchdog scans.
   - Distributed idempotency key management for `ToolGateway`.
3. **Phase 4 (Load Testing & Benchmarking):**
   - Build a comprehensive Locust / Python asynchronous load-testing suite with Smoke, Load, Stress, and Spike profiles.
4. **Phase 5 & 6 (Containerization, Load Balancing & Horizontal Scaling):**
   - Update `Dockerfile` to use multi-stage production build.
   - Configure Nginx upstream load balancer with health checks, failover, connection pooling, and WebSocket proxying.
   - Scale FastAPI backend horizontally across multiple replicas in `docker-compose.prod.yml`.
