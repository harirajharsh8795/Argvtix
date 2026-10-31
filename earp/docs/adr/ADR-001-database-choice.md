# ADR-001: Database Choice — PostgreSQL + SQLAlchemy with SQLite Test Parity

## Status
Accepted

## Context
Proofline needs to store high-throughput execution traces, structured tool execution snapshots, vector embeddings for policy document retrieval (RAG), and transactional ledgers (orders, payments, refunds, inventory).
The database must support:
1. High-throughput writes for distributed agent tracing.
2. Relational integrity for cross-system reconciliation and anomaly detection.
3. Native vector similarity search via `pgvector` for enterprise RAG knowledge bases.
4. Fast, zero-dependency in-memory/file testing for CI/CD and developer local setups.

## Decision
We chose **PostgreSQL 16 with `pgvector`** as the primary production database, orchestrated via **SQLAlchemy 2.0** ORM and Alembic migrations.
For local unit testing and quick developer iteration, we support **SQLite** with dialect abstraction so that tests execute in sub-second times without requiring a live Docker daemon.

## Consequences
- **Positive:** Full ACID compliance, foreign key cascade guarantees, relational JOIN performance for reconciliation, native vector indexing, robust transaction isolation.
- **Trade-off:** Requires Alembic migration discipline across SQLite and PostgreSQL dialect differences (e.g., JSON vs JSONB, DateTime timezone support).
