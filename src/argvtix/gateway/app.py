"""
FastAPI Gateway & Control Plane for ARGVTIX
Exposes REST APIs for:
- Trace ingestion, querying, and aggregation metrics
- Real-time pre-action policy Guard evaluation
- Watchdog background/on-demand scanning and findings management
- Platform & Database health checks
"""

import json
import logging
import os
import secrets
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import case, func, text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

# Structured Audit Logger
logger = logging.getLogger("argvtix.gateway")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [argvtix] %(message)s")
    _log_handler.setFormatter(_log_formatter)
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)

from argvtix.cache import cache_manager
from argvtix.db.models import (
    TraceRecord,
    TraceStepRecord,
    WatchdogFindingRecord,
)
from argvtix.db.session import engine, get_db, init_db
from argvtix.evals.benchmarks.adapters import MockAdapter
from argvtix.evals.benchmarks.runner import BenchmarkRunner
from argvtix.evals.claims import ClaimVerifier
from argvtix.evals.claims.planted_cases import get_planted_cases
from argvtix.evals.passk import PassKRunner
from argvtix.evals.regression import RegressionEngine
from argvtix.guard import (
    ActionGuard,
    ApprovalDecisionRequest,
    ApprovalQueue,
    GuardCheckRequest,
    GuardCheckResponse,
    ToolGateway,
)
from argvtix.replay.engine import ReplayEngine
from argvtix.replay.golden import filter_golden_cases, load_golden_cases
from argvtix.scout import (
    MissingAuthorizationError,
    ScopeConfig,
    ScopeExpiredError,
    ScoutAuditReport,
    ScoutRunner,
    ScoutSafetyController,
    ScoutSafetyViolationError,
    TargetHostNotAllowedError,
    TargetPathNotAllowedError,
)
from argvtix.scout.probes import default_probe_registry
from argvtix.security.auth import (
    Role,
    TokenPayload,
    create_access_token,
    get_current_user,
    require_role,
    verify_credentials,
)
from argvtix.security.dlp import DLPFilter
from argvtix.security.pii import PIIMasker
from argvtix.security.redteam.runner import RedTeamRunner
from argvtix.target_app.agent import ShopOpsAgent
from argvtix.target_app.llm import MockLLM
from argvtix.target_app.rag.policy_docs import POLICY_DOCUMENTS
from argvtix.target_app.spend_guard import spend_guard
from argvtix.trace.schemas import StepType, Trace, TraceStatus
from argvtix.watchdog.alerts import AlertPayload, AlertSeverity, alert_dispatcher
from argvtix.watchdog.anomaly import AnomalyDetector
from argvtix.watchdog.conflicts.benchmark import evaluate_conflict_benchmark
from argvtix.watchdog.conflicts.detector import PolicyConflictDetector
from argvtix.watchdog.engine import WatchdogEngine
from argvtix.watchdog.reconcile.engine import ReconciliationEngine
from argvtix.watchdog.reconcile.schemas import ExternalEntityState
from argvtix.ws.router import router as ws_router

# ---------------------------------------------------------------------------
# Security Middlewares
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects defense-in-depth HTTP security headers into every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss: http: https:; "
            "frame-ancestors 'none';"
        )
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        return response


class MaxPayloadSizeMiddleware(BaseHTTPMiddleware):
    """Restricts inbound request body size to prevent memory exhaustion DoS."""

    MAX_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB threshold

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.MAX_PAYLOAD_BYTES:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": "Payload too large. Maximum permitted body size is 5MB."
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests, response status codes, and execution duration."""

    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now(UTC)
        response = await call_next(request)
        duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000.0
        # Exclude high-frequency health probes from log clutter
        if not request.url.path.endswith("/health"):
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)"
            )
        return response


# ---------------------------------------------------------------------------
# Rate Limiter & Environment Hardening
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])

_env_name = os.getenv("ENVIRONMENT", os.getenv("ARGVTIX_ENV", "development")).lower()
is_production = _env_name in ("production", "prod", "staging")


def verify_startup_configuration() -> None:
    """Validate critical environment configuration and startup invariants.

    Raises RuntimeError if a required production variable is missing or insecure.
    """
    env = os.getenv("ENVIRONMENT", os.getenv("ARGVTIX_ENV", "development")).lower()
    is_prod = env in ("production", "prod", "staging")

    if is_prod:
        from argvtix.db.session import DATABASE_URL

        if not DATABASE_URL or DATABASE_URL.startswith("sqlite"):
            raise RuntimeError(
                "CRITICAL PRODUCTION CONFIGURATION ERROR: Production environment detected, but DATABASE_URL "
                "is missing or pointing to SQLite ('sqlite:///...'). Production requires a managed database (PostgreSQL)."
            )
        from argvtix.security.auth import get_jwt_secret_key

        get_jwt_secret_key()

        admin_pass = os.getenv(
            "ARGVTIX_ADMIN_PASSWORD", os.getenv("PROOFLINE_ADMIN_PASSWORD", "")
        ).strip()
        if not admin_pass:
            raise RuntimeError(
                "CRITICAL PRODUCTION CONFIGURATION ERROR: Production environment detected, but ARGVTIX_ADMIN_PASSWORD "
                "is not configured. Administrative credentials are required for production startup."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables and enforce production startup invariants."""
    verify_startup_configuration()
    init_db()
    yield


app = FastAPI(
    title="ARGVTIX — Enterprise AI Reliability Platform",
    description="High-performance observability, policy guard, evaluation, and watchdog engine for AI agents.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
)

# Attach Rate Limiter exception handler and state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# 2. Request Body Size Limiter
app.add_middleware(MaxPayloadSizeMiddleware)

# 2b. Structured Request & Audit Logging
app.add_middleware(RequestLoggingMiddleware)

# 3. Explicit CORS Policy
_configured_origins = os.getenv(
    "ARGVTIX_ALLOWED_ORIGINS", os.getenv("PROOFLINE_ALLOWED_ORIGINS", "")
)
if _configured_origins:
    allowed_origins = [o.strip() for o in _configured_origins.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://app.argvtix.ai",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-Project-Id"],
)

# Mount real-time WebSocket router
app.include_router(ws_router)

guard_engine = ActionGuard()
watchdog_engine = WatchdogEngine()
pii_masker = PIIMasker()
dlp_filter = DLPFilter(pii_masker=pii_masker)


# ============================================================================
# Health Check Endpoint
# ============================================================================


@app.get("/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
def health_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Platform health check and database connectivity verification."""
    db_healthy = True
    error_msg = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_healthy = False
        error_msg = str(e) if not is_production else "Database connection failure"

    pool = engine.pool
    pool_stats = {
        "pool_size": getattr(pool, "size", lambda: 5)(),
        "checkedin": getattr(pool, "checkedin", lambda: 0)(),
        "checkedout": getattr(pool, "checkedout", lambda: 0)(),
    }

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "database": {
            "connected": db_healthy,
            "error": error_msg,
            "pool": pool_stats,
        },
        "services": {
            "trace_recorder": "active",
            "action_guard": "active",
            "watchdog": "active",
        },
    }


# ============================================================================
# Contact & Enterprise Demo Request API (Cloudflare Turnstile Protected)
# ============================================================================


class ContactSubmissionRequest(BaseModel):
    name: str
    email: str
    company: str
    use_case: str
    turnstile_token: str | None = None
    honeypot: str | None = None


class ContactSubmissionResponse(BaseModel):
    status: str
    submission_id: str
    message: str


def verify_cloudflare_turnstile(token: str, ip: str | None = None) -> bool:
    """Verify Cloudflare Turnstile CAPTCHA token with Cloudflare siteverify endpoint."""
    secret = os.environ.get("CLOUDFLARE_TURNSTILE_SECRET_KEY")
    env = os.getenv("ENVIRONMENT", os.getenv("ARGVTIX_ENV", "development")).lower()
    is_prod = env in ("production", "prod", "staging")

    if not secret:
        if is_prod:
            logger.error(
                "Turnstile verification failed closed: CLOUDFLARE_TURNSTILE_SECRET_KEY not configured in production."
            )
            return False
        # In test / local mode without live Cloudflare credentials, accept test tokens
        return True

    verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    data = {"secret": secret, "response": token}
    if ip:
        data["remoteip"] = ip

    try:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(verify_url, data=encoded, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return bool(result.get("success", False))
    except Exception:
        return False


@app.post(
    "/api/v1/contact",
    response_model=ContactSubmissionResponse,
    tags=["Contact"],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
def submit_contact_form(
    request: Request,
    payload: ContactSubmissionRequest,
    db: Session = Depends(get_db),
) -> ContactSubmissionResponse:
    """Enterprise contact and demonstration request endpoint with anti-abuse controls."""
    # 1. Bot Honeypot Defense
    if payload.honeypot and payload.honeypot.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Automated submission detected.",
        )

    # 2. Field length and format validation
    name = payload.name.strip()
    email = payload.email.strip()
    company = payload.company.strip()
    use_case = payload.use_case.strip()

    if not name or len(name) > 120:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid full name required (max 120 chars).",
        )
    if "@" not in email or "." not in email or len(email) > 180:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid business email required.",
        )
    if not company or len(company) > 120:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Company or organization name required.",
        )
    if not use_case or len(use_case) < 10 or len(use_case) > 2000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please describe your AI agent use case (10-2000 chars).",
        )

    # 3. Cloudflare Turnstile token validation
    client_ip = request.client.host if request.client else None
    env = os.getenv("ENVIRONMENT", os.getenv("ARGVTIX_ENV", "development")).lower()
    is_prod = env in ("production", "prod", "staging")

    if is_prod:
        if not payload.turnstile_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cloudflare Turnstile verification challenge required in production.",
            )
        if not verify_cloudflare_turnstile(payload.turnstile_token, client_ip):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security verification challenge failed. Please refresh and retry.",
            )
    else:
        if os.environ.get("CLOUDFLARE_TURNSTILE_SECRET_KEY") and not payload.turnstile_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cloudflare Turnstile verification challenge required.",
            )
        if payload.turnstile_token and not verify_cloudflare_turnstile(
            payload.turnstile_token, client_ip
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security verification challenge failed. Please refresh and retry.",
            )

    submission_id = f"sub_{int(datetime.now(UTC).timestamp())}_{secrets.token_hex(4)}"
    return ContactSubmissionResponse(
        status="success",
        submission_id=submission_id,
        message="Demo request submitted successfully. Our engineering team will review your architecture and contact you within 24 business hours.",
    )


# ============================================================================
# Trace Observability APIs
# ============================================================================


class TraceIngestResponse(BaseModel):
    trace_id: str
    status: str
    steps_count: int
    message: str


@app.post(
    "/api/v1/traces",
    response_model=TraceIngestResponse,
    tags=["Traces"],
    status_code=status.HTTP_201_CREATED,
)
def ingest_trace(
    trace: Trace,
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> TraceIngestResponse:
    """Ingest a complete AI execution trace with validation."""
    # Ensure aggregates are computed
    trace.compute_aggregates()

    existing = db.query(TraceRecord).filter_by(id=trace.trace_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Trace with ID {trace.trace_id} already exists.",
        )

    # Extract output & error from steps if present
    output_text = None
    output_steps = trace.get_steps_by_type(StepType.OUTPUT)
    if output_steps and output_steps[-1].output:
        output_text = getattr(
            output_steps[-1].output,
            "response_text",
            getattr(output_steps[-1].output, "output_text", None),
        )

    error_msg = None
    error_steps = trace.get_steps_by_type(StepType.ERROR)
    if error_steps and error_steps[-1].error:
        error_msg = error_steps[-1].error.error_message

    workflow_type = trace.metadata.get("workflow_type")
    if not workflow_type and trace.tags:
        workflow_type = trace.tags[0]

    assigned_project_id = (
        user.project_id
        if user.project_id and user.project_id != "default"
        else (getattr(trace, "project_id", "default") or "default")
    )

    # Create root trace record
    record = TraceRecord(
        id=trace.trace_id,
        project_id=assigned_project_id,
        session_id=trace.session_id,
        user_id=trace.customer_id,
        channel=trace.metadata.get("channel", "web"),
        workflow_type=workflow_type,
        status=trace.status.value,
        input_text=trace.input_text,
        output_text=output_text,
        error_message=error_msg,
        total_latency_ms=trace.total_latency_ms,
        total_cost_usd=trace.total_cost_usd,
        total_tokens=trace.total_tokens,
        tags_json=json.dumps(trace.tags),
        metadata_json=json.dumps(trace.metadata),
        created_at=trace.created_at,
        completed_at=trace.completed_at,
    )
    db.add(record)

    # Ingest individual steps
    for step in trace.steps:
        step_rec = TraceStepRecord(
            id=step.step_id,
            trace_id=trace.trace_id,
            step_index=step.step_index,
            step_type=step.step_type.value,
            latency_ms=step.duration_ms or 0.0,
            step_data_json=step.model_dump_json(),
            created_at=step.timestamp,
        )
        db.add(step_rec)

    db.commit()

    # Invalidate cached statistics and spend on new trace ingestion
    cache_manager.delete_pattern("traces:*")
    cache_manager.delete_pattern("spend:*")

    return TraceIngestResponse(
        trace_id=trace.trace_id,
        status=trace.status.value,
        steps_count=len(trace.steps),
        message="Trace successfully recorded.",
    )


@app.get("/api/v1/traces", tags=["Traces"])
def list_traces(
    workflow_type: str | None = None,
    trace_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """List ingested traces with optional filtering and pagination."""
    query = db.query(TraceRecord).filter(TraceRecord.project_id == user.project_id)
    if workflow_type:
        query = query.filter(TraceRecord.workflow_type == workflow_type)
    if trace_status:
        query = query.filter(TraceRecord.status == trace_status)

    total_count = query.count()
    records = query.order_by(TraceRecord.created_at.desc()).offset(offset).limit(limit).all()

    items = [
        {
            "id": r.id,
            "trace_id": r.id,
            "session_id": r.session_id,
            "user_id": r.user_id,
            "workflow_type": r.workflow_type,
            "status": r.status,
            "input_text": r.input_text[:100] + "..." if len(r.input_text) > 100 else r.input_text,
            "output_text": r.output_text[:100] + "..."
            if r.output_text and len(r.output_text) > 100
            else r.output_text,
            "total_latency_ms": r.total_latency_ms,
            "total_cost_usd": r.total_cost_usd,
            "total_tokens": r.total_tokens,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "items": items,
        "traces": items,
    }


@app.get("/api/v1/traces/stats", tags=["Traces"])
def get_trace_stats(
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Return high-level summary metrics across recorded traces for project in a single query with TTL caching."""
    cache_key = f"traces:stats:{user.project_id}"
    cached = cache_manager.get(cache_key)
    if cached is not None:
        return cached

    row = (
        db.query(
            func.count(TraceRecord.id).label("total_traces"),
            func.sum(case((TraceRecord.status == TraceStatus.COMPLETED.value, 1), else_=0)).label(
                "successful"
            ),
            func.avg(TraceRecord.total_latency_ms).label("avg_latency"),
            func.sum(TraceRecord.total_cost_usd).label("total_cost"),
            func.sum(TraceRecord.total_tokens).label("total_tokens"),
        )
        .filter(TraceRecord.project_id == user.project_id)
        .first()
    )

    total_traces = int(row.total_traces or 0)
    if total_traces == 0:
        res = {
            "total_traces": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
        }
        cache_manager.set(cache_key, res, ttl_seconds=5)
        return res

    successful = int(row.successful or 0)
    avg_latency = float(row.avg_latency or 0.0)
    total_cost = float(row.total_cost or 0.0)
    total_tokens = int(row.total_tokens or 0)

    res = {
        "total_traces": total_traces,
        "successful_traces": successful,
        "success_rate": round((successful / total_traces) * 100, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
    }
    cache_manager.set(cache_key, res, ttl_seconds=5)
    return res


@app.get("/api/v1/cache/metrics", tags=["System"])
def get_cache_metrics(
    user: TokenPayload = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    """Return real-time cache observability, hit rates, and capacity metrics."""
    return cache_manager.get_metrics()


@app.get("/api/v1/traces/{trace_id}", tags=["Traces"])
def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve full detail for a trace, including chronological execution steps."""
    record = (
        db.query(TraceRecord)
        .filter(TraceRecord.id == trace_id, TraceRecord.project_id == user.project_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    steps = (
        db.query(TraceStepRecord)
        .filter_by(trace_id=trace_id)
        .order_by(TraceStepRecord.step_index.asc())
        .all()
    )

    parsed_steps = []
    for s in steps:
        parsed_steps.append(
            {
                "step_id": s.id,
                "step_index": s.step_index,
                "step_type": s.step_type,
                "latency_ms": s.latency_ms,
                "data": json.loads(s.step_data_json),
                "timestamp": s.created_at.isoformat() if s.created_at else None,
            }
        )

    return {
        "trace_id": record.id,
        "session_id": record.session_id,
        "user_id": record.user_id,
        "channel": record.channel,
        "workflow_type": record.workflow_type,
        "status": record.status,
        "input_text": record.input_text,
        "output_text": record.output_text,
        "error_message": record.error_message,
        "total_latency_ms": record.total_latency_ms,
        "total_cost_usd": record.total_cost_usd,
        "total_tokens": record.total_tokens,
        "tags": json.loads(record.tags_json) if record.tags_json else [],
        "metadata": json.loads(record.metadata_json) if record.metadata_json else {},
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "steps": parsed_steps,
    }


# ============================================================================
# Action Guard Policy APIs
# ============================================================================


@app.post("/api/v1/guard/check", response_model=GuardCheckResponse, tags=["Guard"])
def check_action_guard(
    request: GuardCheckRequest, db: Session = Depends(get_db)
) -> GuardCheckResponse:
    """Evaluate whether an agent tool call or business action satisfies safety guards."""
    res = guard_engine.evaluate(request, db)
    logger.info(
        f"ActionGuard Decision: {res.decision.value} for tool={request.tool_name} "
        f"customer={getattr(request, 'customer_id', None)} reason='{res.reason}'"
    )
    return res


# ============================================================================
# Watchdog Scanning & Findings APIs
# ============================================================================


@app.post("/api/v1/watchdog/scan", tags=["Watchdog"])
@limiter.limit("15/minute")
def run_watchdog_scan(
    request: Request,
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Trigger an on-demand scan of all data integrity rules against business tables."""
    return watchdog_engine.scan(db, persist=True, project_id=user.project_id)


@app.get("/api/v1/watchdog/findings", tags=["Watchdog"])
def list_watchdog_findings(
    resolved: bool | None = None,
    severity: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """List data anomalies flagged by Watchdog."""
    query = db.query(WatchdogFindingRecord).filter(
        WatchdogFindingRecord.project_id == user.project_id
    )
    if resolved is not None:
        query = query.filter(WatchdogFindingRecord.resolved == resolved)
    if severity:
        query = query.filter(WatchdogFindingRecord.severity == severity)

    total = query.count()
    records = query.order_by(WatchdogFindingRecord.detected_at.desc()).limit(limit).all()

    items = [
        {
            "finding_id": r.id,
            "rule_name": r.rule_name,
            "severity": r.severity,
            "description": r.description,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "trace_id": r.trace_id,
            "details": json.loads(r.details_json) if r.details_json else {},
            "resolved": r.resolved,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in records
    ]

    return {
        "total": total,
        "items": items,
    }


@app.patch("/api/v1/watchdog/findings/{finding_id}/resolve", tags=["Watchdog"])
def resolve_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Mark a watchdog finding as reviewed and resolved."""
    finding = (
        db.query(WatchdogFindingRecord)
        .filter(
            WatchdogFindingRecord.id == finding_id,
            WatchdogFindingRecord.project_id == user.project_id,
        )
        .first()
    )
    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")

    finding.resolved = True
    db.commit()
    return {"status": "success", "message": f"Finding {finding_id} marked as resolved."}


# ---------------------------------------------------------------------------
# Evaluation & Regression Endpoints (Week 5)
# ---------------------------------------------------------------------------


class RunEvalRequest(BaseModel):
    workflow: str | None = None
    max_cases: int | None = None


class RunRegressionRequest(BaseModel):
    workflow: str | None = None
    max_drop_allowed: float = 5.0


@app.post("/api/v1/evals/run", tags=["Evaluations"])
def run_evaluations(
    request: RunEvalRequest = RunEvalRequest(),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run golden benchmark evaluations and return performance summary."""
    cases = (
        filter_golden_cases(workflow=request.workflow) if request.workflow else load_golden_cases()
    )
    if request.max_cases:
        cases = cases[: request.max_cases]

    engine_inst = RegressionEngine(db=db)
    summary, _ = engine_inst.evaluate_config(cases, MockLLM())

    return {
        "total_evals": summary.total_evals,
        "overall_accuracy": summary.overall_accuracy,
        "intent_accuracy": summary.intent_accuracy,
        "guard_alignment": summary.guard_alignment,
        "tool_accuracy": summary.tool_accuracy,
        "p50_latency_ms": summary.p50_latency_ms,
        "p90_latency_ms": summary.p90_latency_ms,
        "p95_latency_ms": summary.p95_latency_ms,
        "total_cost_usd": summary.total_cost_usd,
        "cost_per_100_usd": summary.cost_per_100_usd,
        "language_breakdown": {
            k: {
                "total": v.total,
                "passed": v.passed,
                "accuracy_percent": v.accuracy_percent,
            }
            for k, v in summary.language_breakdown.items()
        },
        "workflow_breakdown": summary.workflow_breakdown,
    }


@app.post("/api/v1/evals/regression", tags=["Evaluations"])
def run_regression_check(
    request: RunRegressionRequest = RunRegressionRequest(),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run regression comparison between baseline and candidate configurations."""
    cases = (
        filter_golden_cases(workflow=request.workflow) if request.workflow else load_golden_cases()
    )
    engine_inst = RegressionEngine(db=db)
    base_llm = MockLLM()
    cand_llm = MockLLM()

    report = engine_inst.compare(
        baseline_llm=base_llm,
        candidate_llm=cand_llm,
        cases=cases,
        max_allowed_drop_percent=request.max_drop_allowed,
    )

    return {
        "verdict": report.verdict,
        "baseline_accuracy": report.baseline_summary.overall_accuracy,
        "candidate_accuracy": report.candidate_summary.overall_accuracy,
        "accuracy_delta": report.accuracy_delta,
        "p95_latency_delta_ms": report.p95_latency_delta_ms,
        "cost_delta_usd": report.cost_delta_usd,
        "regressions_count": len(report.what_got_worse),
        "improvements_count": len(report.what_got_better),
        "what_got_worse": [
            {
                "case_id": w.case_id,
                "ticket_text": w.ticket_text,
                "workflow": w.workflow,
                "reasons": w.failure_reasons,
            }
            for w in report.what_got_worse
        ],
        "what_got_better": [
            {
                "case_id": b.case_id,
                "ticket_text": b.ticket_text,
                "workflow": b.workflow,
            }
            for b in report.what_got_better
        ],
    }


# ---------------------------------------------------------------------------
# Security & PII Sanitization Endpoints (Week 6)
# ---------------------------------------------------------------------------


class MaskTextRequest(BaseModel):
    text: str


class InspectTextRequest(BaseModel):
    text: str


@app.post("/api/v1/security/mask", tags=["Security"])
def mask_sensitive_pii(
    request: MaskTextRequest,
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Sanitize inbound text by masking Aadhaar, Phone, PAN, Email, Card, and UPI."""
    res = pii_masker.mask(request.text)
    return {
        "original_text": res.original_text,
        "masked_text": res.masked_text,
        "has_pii": res.has_pii,
        "entity_count": res.entity_count,
        "types_detected": res.types_detected,
        "entities": [
            {
                "type": e.entity_type,
                "start": e.start,
                "end": e.end,
                "replacement": e.replacement,
            }
            for e in res.entities
        ],
    }


@app.post("/api/v1/security/inspect", tags=["Security"])
def inspect_outbound_text(
    request: InspectTextRequest,
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Audit outbound agent response for PII, system prompt leakage, and credentials."""
    res = dlp_filter.inspect(request.text)
    return {
        "is_safe": res.is_safe,
        "has_critical": res.has_critical,
        "sanitized_text": res.sanitized_text,
        "violations": [
            {
                "rule_name": v.rule_name,
                "severity": v.severity,
                "description": v.description,
                "snippet": v.snippet,
            }
            for v in res.violations
        ],
    }


# ---------------------------------------------------------------------------
# Policy Conflict & Red Team Endpoints (Week 7)
# ---------------------------------------------------------------------------


class ConflictScanRequest(BaseModel):
    include_benchmark: bool = False


class RedTeamRunRequest(BaseModel):
    limit: int | None = None


@app.post("/api/v1/conflicts/scan", tags=["Policy Conflicts"])
@app.post("/api/v1/security/conflicts/scan", tags=["Policy Conflicts"])
def scan_policy_conflicts(
    request: ConflictScanRequest = ConflictScanRequest(),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Audit policy documents for contradictory rules and SLA mismatches."""
    detector = PolicyConflictDetector()
    report = detector.scan_documents(POLICY_DOCUMENTS)

    benchmark_stats = None
    if request.include_benchmark:
        benchmark_stats = evaluate_conflict_benchmark(detector)

    return {
        "total_clauses_scanned": report.total_clauses_scanned,
        "pairs_evaluated": report.pairs_evaluated,
        "conflicts_detected": report.conflicts_detected,
        "consistent_pairs": report.consistent_pairs,
        "unclear_pairs": report.unclear_pairs,
        "findings": [
            {
                "conflict_id": f.conflict_id,
                "topic": f.topic,
                "severity": f.severity,
                "explanation": f.explanation,
                "citation_a": f.citation_a,
                "citation_b": f.citation_b,
            }
            for f in report.findings
        ],
        "benchmark": benchmark_stats,
    }


@app.post("/api/v1/redteam/run", tags=["Security Red Team"])
@app.post("/api/v1/security/redteam/run", tags=["Security Red Team"])
def run_redteam_benchmark(
    request: RedTeamRunRequest = RedTeamRunRequest(),
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Run standardized 40-attack red team suite measuring before vs after defense."""
    runner = RedTeamRunner(db=db)
    scorecard = runner.run_benchmark()

    return {
        "total_attacks": scorecard.total_attacks,
        "baseline_attack_success_rate": f"{scorecard.baseline_attack_success_rate:.1f}%",
        "protected_attack_success_rate": f"{scorecard.protected_attack_success_rate:.1f}%",
        "defense_improvement": f"+{scorecard.defense_improvement_percent:.1f}%",
        "baseline_blocked": scorecard.baseline_blocked_count,
        "protected_blocked": scorecard.protected_blocked_count,
        "category_breakdown": {
            k: {
                "total": v.total,
                "baseline_blocked": v.baseline_blocked,
                "protected_blocked": v.protected_blocked,
                "baseline_success_rate": f"{v.baseline_success_rate_percent:.1f}%",
                "protected_success_rate": f"{v.protected_success_rate_percent:.1f}%",
            }
            for k, v in scorecard.category_breakdown.items()
        },
    }


# ---------------------------------------------------------------------------
# Claim-vs-State Verification & pass^k Endpoints (Sprint A1)
# ---------------------------------------------------------------------------


class VerifyClaimsRequest(BaseModel):
    agent_response: str | None = None
    response_text: str | None = None
    tool_records: list[dict[str, Any]] = []
    state_snapshot: dict[str, Any] | list[dict[str, Any]] | None = None


class PassKRunRequest(BaseModel):
    k: int = 5
    workflow: str | None = None


@app.post("/api/v1/evals/verify-claims", tags=["Evals"])
def verify_claims_endpoint(
    request: VerifyClaimsRequest,
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Deterministically verify factual claims in agent response against tool/DB state."""
    agent_resp = (request.agent_response or request.response_text or "").strip()
    tools = list(request.tool_records)
    if request.state_snapshot:
        if isinstance(request.state_snapshot, dict):
            # Transform database state snapshot into verifiable tool/entity log
            tools.append(
                {
                    "tool_name": "database_snapshot",
                    "tool_args": {"order_id": request.state_snapshot.get("order_id", "entity")},
                    "tool_result": request.state_snapshot,
                    "is_success": (
                        request.state_snapshot.get("refund_status") not in ("failed", "error")
                        and request.state_snapshot.get("status") not in ("failed", "error")
                    ),
                }
            )
        elif isinstance(request.state_snapshot, list):
            tools.extend(request.state_snapshot)

    verifier = ClaimVerifier()
    report = verifier.verify(
        agent_response=agent_resp,
        tool_records=tools,
    )
    res = report.model_dump()
    overall = (
        "verified"
        if report.violations_count == 0 and report.verified_count > 0
        else "hallucination"
        if report.violations_count > 0
        else "neutral"
    )
    res["overall_verdict"] = overall
    res["claims"] = [
        {
            "claim_id": r.claim_id,
            "claim_type": r.claim.claim_type.value
            if hasattr(r.claim.claim_type, "value")
            else str(r.claim.claim_type),
            "claim_text": r.claim.source_text,
            "stated_status": r.claim.claimed_status,
            "verdict": r.verdict.value if hasattr(r.verdict, "value") else str(r.verdict),
            "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
            "explanation": r.explanation,
        }
        for r in report.results
    ]
    logger.info(
        f"ClaimVerifier: agent_resp='{agent_resp[:40]}...' claims={report.total_claims} "
        f"verified={report.verified_count} violations={report.violations_count} verdict={overall}"
    )
    return res


@app.get("/api/v1/evals/planted-scenarios", tags=["Evals"])
def list_planted_scenarios(
    user: TokenPayload = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    """Retrieve all 30 planted failure scenarios across the 6 failure categories."""
    scenarios = get_planted_cases()
    return {
        "total_scenarios": len(scenarios),
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "category": s.category.value,
                "domain": s.domain,
                "language": s.language,
                "description": s.description,
                "agent_response": s.agent_response,
                "tool_records": s.tool_records,
                "expected_verdict": s.expected_verdict.value,
            }
            for s in scenarios
        ],
    }


@app.post("/api/v1/evals/passk", tags=["Evals"])
def run_passk_endpoint(
    request: PassKRunRequest = PassKRunRequest(),
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Run pass^k multi-trial reliability evaluation across golden workflows."""
    cases = (
        filter_golden_cases(workflow=request.workflow) if request.workflow else load_golden_cases()
    )
    llm = MockLLM()
    replayer = ReplayEngine(db=db, default_llm=llm)

    # Wrap each golden case into an evaluator function
    eval_cases = []
    for c in cases[:15]:  # Run on representative slice for fast API response

        def make_eval(case):
            return lambda: replayer.replay_case(case, llm=llm).is_passed

        eval_cases.append((c.id, make_eval(c)))

    runner = PassKRunner(k=request.k)
    report = runner.run(eval_cases)
    res = report.model_dump()
    res["pass_pow_k"] = report.pass_hat_k
    res["total_evaluations"] = report.total_cases
    logger.info(
        f"PassK Evaluation: k={request.k} cases={report.total_cases} "
        f"pass^k={report.pass_hat_k}% flake={report.flake_rate}%"
    )
    return res


# ---------------------------------------------------------------------------
# Tool Gateway MCP Proxy & Human Approval Endpoints (Sprint A2)
# ---------------------------------------------------------------------------


class GatewayCallRequest(BaseModel):
    tool_name: str
    params: dict[str, Any] = {}
    idempotency_key: str | None = None


@app.post("/api/v1/guard/gateway/call", tags=["Tool Gateway"])
@limiter.limit("60/minute")
def call_tool_gateway(
    request: Request,
    body: GatewayCallRequest,
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Execute a tool through the ToolGateway MCP proxy with pre-action Guard enforcement."""
    gateway = ToolGateway()
    result = gateway.call(
        tool_name=body.tool_name,
        params=body.params,
        db=db,
        idempotency_key=body.idempotency_key,
    )
    return result.model_dump()


@app.get("/api/v1/guard/approvals", tags=["Guard Approvals"])
def list_approvals_endpoint(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    """List pending or filtered human-in-the-loop approval requests."""
    queue = ApprovalQueue()
    records = queue.list_all(
        db=db, status=status, limit=limit, offset=offset, project_id=user.project_id
    )
    return {
        "total": len(records),
        "approvals": [
            {
                "id": r.id,
                "action_type": r.action_type,
                "tool_name": r.tool_name,
                "entity_id": r.entity_id,
                "customer_id": r.customer_id,
                "amount": r.amount,
                "payload": json.loads(r.payload_json) if r.payload_json else {},
                "status": r.status,
                "guard_reasons": r.guard_reasons,
                "risk_level": r.risk_level,
                "reviewer_id": r.reviewer_id,
                "reviewer_notes": r.reviewer_notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            }
            for r in records
        ],
    }


@app.post("/api/v1/guard/approvals/{approval_id}/approve", tags=["Guard Approvals"])
def approve_request_endpoint(
    approval_id: str,
    request: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Human reviewer approves an action proposal, triggering ToolGateway execution."""
    queue = ApprovalQueue()
    gateway = ToolGateway(approval_queue=queue)
    reviewer_identity = user.sub or request.reviewer_id or "authenticated_operator"
    try:
        updated_record, exec_result = queue.approve(
            approval_id=approval_id,
            reviewer_id=reviewer_identity,
            notes=request.notes,
            db=db,
            gateway=gateway,
            project_id=user.project_id,
        )
        logger.info(
            f"Approval Decision: {approval_id} -> APPROVED by reviewer={reviewer_identity} notes='{request.notes}'"
        )
        return {
            "status": "success",
            "approval_status": updated_record.status,
            "approval_id": updated_record.id,
            "execution_result": exec_result.data if hasattr(exec_result, "data") else exec_result,
        }
    except ValueError as e:
        err_msg = str(e)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in err_msg.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=err_msg)


@app.post("/api/v1/guard/approvals/{approval_id}/reject", tags=["Guard Approvals"])
def reject_request_endpoint(
    approval_id: str,
    request: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(require_role(Role.OPERATOR)),
) -> dict[str, Any]:
    """Human reviewer rejects an action proposal."""
    queue = ApprovalQueue()
    reviewer_identity = user.sub or request.reviewer_id or "authenticated_operator"
    try:
        updated_record = queue.reject(
            approval_id=approval_id,
            reviewer_id=reviewer_identity,
            reason=request.notes or "Rejected by human reviewer",
            db=db,
            project_id=user.project_id,
        )
        logger.info(
            f"Approval Decision: {approval_id} -> REJECTED by reviewer={reviewer_identity} reason='{updated_record.reviewer_notes}'"
        )
        return {
            "status": "success",
            "approval_status": updated_record.status,
            "approval_id": updated_record.id,
            "reasons": updated_record.reviewer_notes,
        }
    except ValueError as e:
        err_msg = str(e)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in err_msg.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=err_msg)


# ============================================================================
# Sprint A4 Endpoints: Anomaly Detection, Reconciliation, Alerts, Auth, Spend
# ============================================================================


class AuthTokenRequest(BaseModel):
    username: str
    password: str
    project_id: str = "default"
    role: str = "admin"


class ReconcileRequest(BaseModel):
    external_states: list[ExternalEntityState] = []
    persist_findings: bool = True


class AlertCreateRequest(BaseModel):
    title: str
    message: str
    severity: str = "warning"
    source: str = "manual"
    metadata: dict[str, Any] = {}


@app.post("/api/v1/auth/token", tags=["Authentication"])
@limiter.limit("15/minute")
def issue_token_endpoint(
    request: Request,
    body: AuthTokenRequest,
) -> dict[str, Any]:
    """Issue a signed JWT access token for user and project isolation."""
    try:
        role_enum = Role(body.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{body.role}'. Valid roles are: {[r.value for r in Role]}",
        )

    is_valid, granted_role, reason = verify_credentials(
        username=body.username,
        password=body.password,
        requested_role=role_enum,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {reason}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=body.username,
        project_id=body.project_id,
        role=granted_role,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": granted_role.value,
        "project_id": body.project_id,
        "user_id": body.username,
    }


@app.get("/api/v1/watchdog/anomaly/report", tags=["Watchdog Anomaly"])
def get_anomaly_report_endpoint(
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Evaluates sliding window time-series and returns live anomaly detection report."""
    detector = AnomalyDetector()
    report = detector.scan_db_metrics(db)
    return report.model_dump()


@app.post("/api/v1/watchdog/reconcile", tags=["Watchdog Reconcile"])
def run_reconciliation_endpoint(
    request: ReconcileRequest = ReconcileRequest(),
    db: Session = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Executes cross-system reconciliation audit across DB, CRM, and ERP."""
    engine_inst = ReconciliationEngine(db=db)
    result = engine_inst.run_reconciliation(
        external_states=request.external_states,
        persist_findings=request.persist_findings,
    )
    if result.total_discrepancies > 0:
        alert_dispatcher.dispatch(
            AlertPayload(
                title=f"Reconciliation Discrepancies ({result.total_discrepancies})",
                message=f"Found {result.total_discrepancies} state mismatches across internal and external ledgers.",
                severity=AlertSeverity.CRITICAL,
                source="reconcile",
                metadata={"total_discrepancies": result.total_discrepancies},
            )
        )
    return result.model_dump()


@app.get("/api/v1/watchdog/alerts", tags=["Watchdog Alerts"])
def get_alerts_endpoint(
    limit: int = Query(50, ge=1, le=200),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieves recent alerts from the multi-channel in-memory dispatch queue."""
    alerts = alert_dispatcher.get_recent_alerts(limit=limit)
    return {
        "total_alerts": len(alerts),
        "alerts": [a.model_dump() for a in alerts],
    }


@app.post("/api/v1/watchdog/alerts", tags=["Watchdog Alerts"])
def create_alert_endpoint(
    request: AlertCreateRequest,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually dispatch an alert event into the multi-channel pipeline."""
    try:
        sev = AlertSeverity(request.severity.lower())
    except ValueError:
        sev = AlertSeverity.WARNING

    payload = AlertPayload(
        title=request.title,
        message=request.message,
        severity=sev,
        source=request.source,
        metadata=request.metadata,
    )
    status_map = alert_dispatcher.dispatch(payload)
    return {
        "status": "success",
        "alert_id": payload.alert_id,
        "dispatch_status": status_map,
    }


@app.get("/api/v1/spend/summary", tags=["Spend Guard"])
def get_spend_summary_endpoint(
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns current daily and monthly LLM spend metrics and cap enforcement status."""
    return spend_guard.get_summary()


# ============================================================================
# Argvtix Scout Endpoints (Permission-First Legal Model)
# ============================================================================

scout_reports: dict[str, ScoutAuditReport] = {}
scout_active_safety_controllers: list[ScoutSafetyController] = []


class ScoutRunRequest(BaseModel):
    scope: ScopeConfig
    category: str | None = None
    max_probes: int | None = None


class ScoutAbortRequest(BaseModel):
    reason: str = "Operator manual emergency abort"


class ScoutSignoffRequest(BaseModel):
    approved: bool
    notes: str = ""


@app.get("/api/v1/scout/probes", tags=["Argvtix Scout"])
def list_scout_probes_endpoint(
    category: str | None = Query(None),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Lists all available audit probe scenarios and category coverage."""
    from argvtix.scout.probes.base import ProbeCategory

    cat_filter = None
    if category:
        try:
            cat_filter = ProbeCategory(category)
        except ValueError:
            pass

    probes = default_probe_registry.filter(category=cat_filter)
    return {
        "total_probes": len(probes),
        "category_counts": default_probe_registry.get_category_counts(),
        "probes": [p.model_dump() for p in probes],
    }


@app.post("/api/v1/scout/run", tags=["Argvtix Scout"])
def run_scout_audit_endpoint(
    request: ScoutRunRequest,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Executes permission-governed security & reliability audit against target agent."""
    safety_ctrl = ScoutSafetyController(
        max_rpm=request.scope.max_rpm,
        max_turns_per_conversation=request.scope.max_turns_per_conversation,
        max_conversations=request.scope.max_conversations,
    )
    scout_active_safety_controllers.append(safety_ctrl)

    runner = ScoutRunner(scope=request.scope, safety_controller=safety_ctrl)

    # Initialize agent for internal target or mock
    shopops_agent = ShopOpsAgent(llm_client=MockLLM())

    def target_caller(user_input: str, history: list[dict[str, str]]) -> str:
        res = shopops_agent.handle_user_message(user_input, thread_id="scout-audit-run")
        return res.get("response", "")

    from argvtix.scout.probes.base import ProbeCategory

    selected = None
    if request.category:
        try:
            selected = default_probe_registry.filter(category=ProbeCategory(request.category))
        except ValueError:
            pass

    if request.max_probes and selected:
        selected = selected[: request.max_probes]
    elif request.max_probes:
        selected = default_probe_registry.list_all()[: request.max_probes]

    try:
        report = runner.run_audit(target_fn=target_caller, selected_probes=selected)
    except TargetHostNotAllowedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Egress forbidden: {str(e)}"
        )
    except (ScopeExpiredError, MissingAuthorizationError, TargetPathNotAllowedError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid scope: {str(e)}"
        )
    except ScoutSafetyViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Safety control violation: {str(e)}"
        )
    finally:
        if safety_ctrl in scout_active_safety_controllers:
            scout_active_safety_controllers.remove(safety_ctrl)

    scout_reports[report.report_id] = report
    return report.model_dump()


@app.post("/api/v1/scout/abort", tags=["Argvtix Scout"])
def abort_scout_audit_endpoint(
    request: ScoutAbortRequest = ScoutAbortRequest(),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Emergency kill switch: Halts all running Scout probes and audits within 5 seconds."""
    halted_count = 0
    for ctrl in scout_active_safety_controllers:
        ctrl.trigger_kill_switch(reason=request.reason)
        halted_count += 1
    return {
        "status": "aborted",
        "halted_controllers": halted_count,
        "reason": request.reason,
    }


@app.get("/api/v1/scout/reports", tags=["Argvtix Scout"])
def list_scout_reports_endpoint(
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieves list of generated Scout audit reports."""
    return {
        "total_reports": len(scout_reports),
        "reports": [
            {
                "report_id": r.report_id,
                "scope_id": r.scope_id,
                "target_name": r.target_name,
                "grade": r.grade.value,
                "status": r.status.value,
                "pass_rate_percent": r.pass_rate_percent,
                "total_probes": r.total_probes,
                "critical_violations": r.critical_violations,
                "generated_at": r.generated_at.isoformat(),
            }
            for r in scout_reports.values()
        ],
    }


@app.get("/api/v1/scout/reports/{report_id}", tags=["Argvtix Scout"])
def get_scout_report_endpoint(
    report_id: str,
    format: str = Query("json"),
    user: TokenPayload = Depends(get_current_user),
) -> Any:
    """Retrieves specific Scout audit report in JSON, Markdown, or HTML format."""
    report = scout_reports.get(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Report '{report_id}' not found."
        )

    if format.lower() == "markdown":
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(content=report.to_markdown())
    elif format.lower() == "html":
        from fastapi.responses import HTMLResponse

        return HTMLResponse(content=report.to_html())
    return report.model_dump()


@app.post("/api/v1/scout/reports/{report_id}/signoff", tags=["Argvtix Scout"])
def signoff_scout_report_endpoint(
    report_id: str,
    request: ScoutSignoffRequest,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Human review gate sign-off for a Scout audit report."""
    report = scout_reports.get(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Report '{report_id}' not found."
        )

    report.sign_off(
        reviewer_id=user.sub,
        approved=request.approved,
        notes=request.notes,
    )
    return {
        "status": "success",
        "report_id": report_id,
        "audit_status": report.status.value,
        "reviewed_by": report.reviewed_by,
        "reviewed_at": report.reviewed_at.isoformat() if report.reviewed_at else None,
    }


# ============================================================================
# Multi-Model Benchmark Endpoint (Feature: Live LLM Benchmarking)
# ============================================================================


class BenchmarkRunRequest(BaseModel):
    models: list[str] = ["mock"]  # Use MockAdapter by default to avoid API keys requirement
    workflow: str | None = None
    max_cases: int | None = None


@app.post("/api/v1/benchmarks/run", tags=["Benchmarks"])
def run_benchmark_endpoint(
    request: BenchmarkRunRequest = BenchmarkRunRequest(),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Run the golden evaluation suite across multiple LLM adapters.

    By default runs with the deterministic MockAdapter (no API key needed).
    Pass model names ['gemini', 'claude', 'gpt4o'] to run live evaluations
    (requires corresponding API keys in environment).
    """
    from argvtix.evals.benchmarks.adapters import (
        ClaudeAdapter,
        GeminiAdapter,
        GPT4oAdapter,
        LiteLLMAdapter,
    )

    _adapter_map = {
        "mock": MockAdapter,
        "gemini": GeminiAdapter,
        "claude": ClaudeAdapter,
        "gpt4o": GPT4oAdapter,
        "gpt4o-mini": lambda: LiteLLMAdapter("gpt-4o-mini"),
    }

    adapters = []
    for name in request.models:
        factory = _adapter_map.get(name)
        if factory:
            adapters.append(factory())

    if not adapters:
        adapters = [MockAdapter()]

    runner = BenchmarkRunner(adapters=adapters)
    run = runner.run(workflow=request.workflow, max_cases=request.max_cases)

    return {
        "run_id": run.run_id,
        "timestamp": run.timestamp,
        "total_models": run.total_models,
        "total_cases": run.total_cases,
        "winner_accuracy": run.winner_accuracy,
        "winner_cost": run.winner_cost,
        "winner_latency": run.winner_latency,
        "models": [
            {
                "model_id": r.model_id,
                "accuracy_pct": round(r.accuracy_pct, 2),
                "p50_latency_ms": round(r.p50_latency_ms, 1),
                "p90_latency_ms": round(r.p90_latency_ms, 1),
                "total_cost_usd": round(r.total_cost_usd, 6),
                "passed": r.passed,
                "failed": r.failed,
                "errors": r.error_count,
            }
            for r in run.ranked_by_accuracy()
        ],
    }


# ============================================================================
# Static Files & SPA Frontend Serving (Local & Self-Hosted Fallback)
# ============================================================================

from pathlib import Path

_ui_dist_dir = Path(__file__).resolve().parent.parent.parent.parent / "ui" / "dist"
if _ui_dist_dir.is_dir() and (_ui_dist_dir / "index.html").is_file():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    if (_ui_dist_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ui_dist_dir / "assets")), name="ui-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_frontend(full_path: str):
        if full_path.startswith(
            ("api", "health", "ready", "metrics", "docs", "redoc", "openapi.json")
        ):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        target_file = _ui_dist_dir / full_path
        if full_path and target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(_ui_dist_dir / "index.html")
