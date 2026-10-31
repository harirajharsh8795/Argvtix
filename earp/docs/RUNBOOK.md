# Proofline EARP — Operations & Deployment Runbook (RUNBOOK.md)

**System:** Proofline EARP (*Enterprise AI Reliability & Action Guard Platform*)  
**Version:** 1.0.0-rc  
**Last Updated:** October 29, 2026  
**Audience:** Platform Engineers, SREs, DevSecOps, Release Managers  

---

## 1. Quick Reference: Environment Variables

All configuration is supplied via environment variables. See [`.env.example`](file:///e:/Desktop/AI%20FDE/fde%20project%201/earp/.env.example) for non-sensitive sample configurations.

| Variable Name | Required In | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | All | `development` | Operating mode: `development`, `staging`, `production`. |
| `DATABASE_URL` | Staging/Prod | `sqlite:///./earp.db` | PostgreSQL connection string (`postgresql://user:pass@host:5432/db`). Enforces PostgreSQL in production. |
| `REDIS_URL` | Staging/Prod | None | Distributed Redis 7.2 endpoint (`redis://:pass@host:6379/0`). Provides cross-replica idempotency. |
| `PROOFLINE_JWT_SECRET` | Production | Dev fallback | Min 32-byte high-entropy key for signing HS256 tokens. Startup fails if weak secret in prod. |
| `PROOFLINE_AUTH_ENABLED`| Dev/Staging | `false` | When true, enforces Bearer JWT. **In production, always enforced unconditionally.** |
| `CLOUDFLARE_TURNSTILE_SECRET_KEY` | Production | None | Cloudflare Turnstile anti-bot site secret. Public forms fail-closed in prod if missing. |
| `PROOFLINE_ADMIN_PASSWORD` | Production | None | Initial admin credential for bootstrapping enterprise accounts. |
| `PROOFLINE_OPERATOR_PASSWORD` | Production | None | Initial operator credential for human approval workflows. |
| `PROOFLINE_DAILY_LLM_CAP_USD` | All | `50.0` | Thread-safe daily USD spending limit for AI model invocations. |
| `PROOFLINE_MONTHLY_LLM_CAP_USD` | All | `500.0` | Thread-safe monthly USD spending limit for AI model invocations. |
| `DB_POOL_SIZE` | Production | `20` | Bounded database connection pool size. |
| `DB_MAX_OVERFLOW` | Production | `20` | Maximum temporary connection overflow. |

---

## 2. Local Development Setup

### 2.1 Backend Setup
```bash
# 1. Navigate to earp root
cd earp

# 2. Activate virtual environment
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -e .

# 4. Run database migrations
python -m alembic upgrade head

# 5. Start API server with auto-reload
python -m uvicorn earp.gateway.app:app --host 127.0.0.1 --port 8000 --reload
```
API Docs available at: `http://127.0.0.1:8000/docs`

### 2.2 Frontend Setup
```bash
# 1. Navigate to UI directory
cd earp/ui

# 2. Install packages
npm install

# 3. Start development server
npm run dev
```
Console available at: `http://127.0.0.1:5173/`

---

## 3. Database Administration & Migration Runbook

### 3.1 Migration Commands (Alembic)
```bash
# Upgrade to latest migration (Head)
python -m alembic upgrade head

# Check current database revision
python -m alembic current

# Rollback one migration step
python -m alembic downgrade -1

# Generate new migration after model edits
python -m alembic revision -m "description_of_change"
```

### 3.2 Database Migration Ordering
1. `001_initial_schema.py`: Base tables (customers, products, orders, payments, refunds, traces).
2. `002_add_approval_queue.py`: Human-in-the-Loop review queue.
3. `003_add_project_id.py`: Multi-tenant project scoping.
4. `004_performance_indexes.py`: 12 composite & status indexes.
5. `005_add_refund_idempotency_key.py`: Atomic database-level idempotency key & unique constraint.

---

## 4. Backup & Disaster Recovery Procedures

### 4.1 Production PostgreSQL Backup
```bash
# Online hot backup with custom format (compressed)
pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -Fc -f "/backups/proofline_$(date +%Y%m%d_%H%M%S).dump"

# S3 Archive upload
aws s3 cp /backups/proofline_*.dump s3://enterprise-proofline-backups/pg/
```

### 4.2 Production PostgreSQL Restore
```bash
# 1. Create target recovery database if needed
createdb -h $POSTGRES_HOST -U $POSTGRES_USER proofline_recovery

# 2. Restore schema and data
pg_restore -h $POSTGRES_HOST -U $POSTGRES_USER -d proofline_recovery --clean --if-exists /backups/proofline_snapshot.dump

# 3. Verify row counts and integrity
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d proofline_recovery -c "SELECT count(*) FROM orders; SELECT count(*) FROM refunds;"
```

### 4.3 SQLite Backup (Local Dev / Staging)
```bash
python -c "
import sqlite3
src = sqlite3.connect('earp.db')
bck = sqlite3.connect('earp_backup.db')
src.backup(bck)
bck.close()
src.close()
"
```

---

## 5. Docker & Multi-Replica Deployment

### 5.1 Staging / Production Launch
```bash
# Build and run multi-container cluster
docker-compose -f docker-compose.prod.yml up -d --build

# Scale backend API to 5 replicas
docker-compose -f docker-compose.prod.yml up -d --scale api=5
```

### 5.2 Container Health Check Probes
- **HTTP Liveness:** `GET /health` (expects status 200, returns DB & Cache latency).
- **Cache Metrics:** `GET /api/v1/cache/metrics` (returns hits, misses, hit ratio).
- **Watchdog Engine:** `GET /api/v1/watchdog/findings` (confirms database query execution).

---

## 6. Rollback & Incident Response

### 6.1 Emergency Service Kill Switch (Scout / Agent)
If an autonomous agent exhibits rogue behavior:
1. **File Trigger:** Create `.scout_kill` in the application working directory.
2. **Environment Trigger:** Set `PROOFLINE_SCOUT_KILL=1` and restart containers.
3. **HTTP Override:** Operators can reject pending approval items on `/guard`.

### 6.2 Application Rollback Procedure
1. If schema migration rollback is safe:
   ```bash
   docker exec -it proofline-migration python -m alembic downgrade -1
   ```
2. Re-deploy prior stable container tag:
   ```bash
   docker service update --image registry.enterprise.internal/proofline-api:v1.0.0-previous proofline_api
   ```
3. Invalidate Redis application caches:
   ```bash
   redis-cli -u $REDIS_URL FLUSHDB
   ```

---

## 7. Troubleshooting Common Scenarios

| Symptom | Cause | Resolution |
| :--- | :--- | :--- |
| **Startup fails with `CRITICAL PRODUCTION CONFIGURATION ERROR`** | `ENVIRONMENT=production` set while `DATABASE_URL` is SQLite. | Supply managed PostgreSQL URL: `postgresql://user:pass@host:5432/db`. |
| **Startup fails with `insecure default secret`** | Production using default dev JWT secret. | Generate 32+ byte secret (`openssl rand -hex 32`) and assign to `PROOFLINE_JWT_SECRET`. |
| **Public contact form returns HTTP 400 in prod** | Turnstile secret missing or captcha token omitted. | Ensure `CLOUDFLARE_TURNSTILE_SECRET_KEY` is configured in production container environment. |
| **Duplicate refund attempt returns prior ID** | Expected behavior: Atomic idempotency resolution. | EARP ToolGateway and database unique constraints prevent duplicate payment commits. |
| **Redis connection drops** | Network partition or Redis restart. | Automatic failover: `CacheManager` routes reads/writes to in-memory cache without throwing 500s. |
