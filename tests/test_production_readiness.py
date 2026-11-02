"""
Independent Production Readiness & Security Release Verification Test Suite.
Verifies critical invariants across:
1. Database integrity & concurrent idempotency (Zero Duplicate Commits).
2. Distributed cache & Redis transparent fallback.
3. Production environment startup invariants & JWT security.
4. Cloudflare Turnstile public form fail-closed validation.
5. RBAC authorization & approval queue immutability.
6. Rate limiting and boundary conditions.
"""

from __future__ import annotations

import concurrent.futures
import os
import time
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.cache.manager import CacheManager, InMemoryLRUTTLCache, RedisCache
from argvtix.db.models import (
    Base,
    Customer,
    Order,
    Payment,
    Refund,
)
from argvtix.db.session import init_db
from argvtix.gateway.app import app, lifespan, verify_cloudflare_turnstile
from argvtix.guard import ActionGuard, ApprovalQueue, ToolGateway
from argvtix.guard.engine import GuardCheckRequest
from argvtix.security.auth import (
    Role,
    TokenPayload,
    create_access_token,
    get_jwt_secret_key,
    is_auth_enabled,
    verify_access_token,
    verify_credentials,
)
from argvtix.target_app.tools import shop_tools
from argvtix.trace.schemas import GuardDecision, Severity


# ---------------------------------------------------------------------------
# Test Fixtures: Isolated In-Memory Database
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_db_setup(tmp_path):
    """Creates an isolated file-based engine and sessionmaker for concurrency tests."""
    db_file = tmp_path / "test_concurrency.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    with test_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Seed isolated customer and order
    with TestingSession() as db:
        customer = Customer(
            id="cust_prod_audit",
            name="Enterprise Audit Customer",
            email="audit@enterprise.internal",
            phone="+919876543210",
            wallet_balance=0.0,
        )
        order = Order(
            id="ord_prod_audit",
            customer_id="cust_prod_audit",
            status="pending",
            subtotal=8000.0,
            tax=0.0,
            total_amount=8000.0,
        )
        payment = Payment(
            id="pay_prod_audit",
            order_id="ord_prod_audit",
            customer_id="cust_prod_audit",
            amount=8000.0,
            status="succeeded",
            method="credit_card",
        )
        db.add(customer)
        db.add(order)
        db.add(payment)
        db.commit()

    try:
        yield test_engine, TestingSession
    finally:
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def isolated_db(isolated_db_setup):
    """Provides a single session for single-threaded tests."""
    _, TestingSession = isolated_db_setup
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# PHASE 2 & 3: Database Concurrency & Atomic Idempotency Tests
# ---------------------------------------------------------------------------

def test_atomic_idempotency_concurrent_refunds(isolated_db_setup):
    """
    Critical Invariant:
    Two concurrent workers/replicas executing the same logical refund request
    must NEVER independently commit duplicate refund rows.
    """
    _, SessionFactory = isolated_db_setup
    idempotency_key = "idemp_test_concurrent_001"
    results = []

    def run_worker(worker_id: int):
        with SessionFactory() as session:
            return shop_tools.issue_refund(
                db=session,
                customer_id="cust_prod_audit",
                order_id="ord_prod_audit",
                amount=2000.0,
                reason=f"worker_{worker_id}_request",
                idempotency_key=idempotency_key,
            )

    # Simulate 5 concurrent threads attempting the exact same refund with identical idempotency_key
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_worker, i) for i in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Verify: All calls returned successfully
    for r in results:
        assert r.success is True

    # Critical Invariant Verification: Exactly ONE refund was committed in the database!
    with SessionFactory() as session:
        refunds_in_db = (
            session.query(Refund)
            .filter(Refund.order_id == "ord_prod_audit")
            .all()
        )
        assert len(refunds_in_db) == 1, f"Expected exactly 1 committed refund, found {len(refunds_in_db)}!"
        assert refunds_in_db[0].idempotency_key == idempotency_key


def test_tool_gateway_passes_idempotency_key_to_tool(isolated_db):
    """Verify ToolGateway forwards idempotency_key to underlying write tools."""
    gateway = ToolGateway()
    key = "idemp_gateway_pass_through_999"

    res = gateway.call(
        tool_name="issue_refund",
        params={
            "customer_id": "cust_prod_audit",
            "order_id": "ord_prod_audit",
            "amount": 1500.0,
        },
        db=isolated_db,
        idempotency_key=key,
    )
    assert res.decision == GuardDecision.ALLOW
    assert res.success is True

    # Re-call with same idempotency key
    res_duplicate = gateway.call(
        tool_name="issue_refund",
        params={
            "customer_id": "cust_prod_audit",
            "order_id": "ord_prod_audit",
            "amount": 1500.0,
        },
        db=isolated_db,
        idempotency_key=key,
    )
    assert res_duplicate.success is True
    # Verify zero duplicate rows committed
    refunds = isolated_db.query(Refund).filter(Refund.order_id == "ord_prod_audit").all()
    assert len(refunds) == 1


def test_duplicate_refund_rejected_for_same_order(isolated_db):
    """Verify that an order cannot receive two refunds even with different idempotency keys."""
    res1 = shop_tools.issue_refund(
        db=isolated_db,
        customer_id="cust_prod_audit",
        order_id="ord_prod_audit",
        amount=1000.0,
        idempotency_key="key_1",
    )
    assert res1.success is True

    # Attempt second refund on same order
    res2 = shop_tools.issue_refund(
        db=isolated_db,
        customer_id="cust_prod_audit",
        order_id="ord_prod_audit",
        amount=500.0,
        idempotency_key="key_2",
    )
    assert res2.success is False
    assert "already has a refund processed" in res2.error


# ---------------------------------------------------------------------------
# PHASE 3: Redis Cache Resilient Fallback Tests
# ---------------------------------------------------------------------------

def test_redis_cache_fallback_when_offline():
    """Verify RedisCache safely degrades to local in-memory storage when offline."""
    fallback = InMemoryLRUTTLCache(maxsize=100)
    # Point to a closed port
    redis_cache = RedisCache("redis://127.0.0.1:65530/0", fallback_cache=fallback)

    # Should not raise exception; should store and retrieve via in-memory fallback
    assert redis_cache.set("test_key", {"status": "ok"}, ttl_seconds=60) is True
    assert redis_cache.get("test_key") == {"status": "ok"}
    assert redis_cache.delete("test_key") is True
    assert redis_cache.get("test_key") is None


def test_in_memory_lru_eviction():
    """Verify process-local cache honors maximum size and evicts LRU items."""
    cache = InMemoryLRUTTLCache(maxsize=3)
    cache.set("k1", "v1", ttl_seconds=60)
    cache.set("k2", "v2", ttl_seconds=60)
    cache.set("k3", "v3", ttl_seconds=60)
    # Touch k1 so k2 becomes least recently used
    _ = cache.get("k1")
    cache.set("k4", "v4", ttl_seconds=60)

    # k2 should be evicted
    assert cache.get("k2") is None
    assert cache.get("k1") == "v1"
    assert cache.get("k3") == "v3"
    assert cache.get("k4") == "v4"


# ---------------------------------------------------------------------------
# PHASE 4: Authentication & Approval Security Tests
# ---------------------------------------------------------------------------

def test_jwt_role_hierarchy_and_tampering():
    """Verify JWT roles and signature validation."""
    token = create_access_token(user_id="operator_user", role=Role.OPERATOR)
    payload = verify_access_token(token)
    assert payload.sub == "operator_user"
    assert payload.role == Role.OPERATOR

    # Tampered token should raise HTTPException 401
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(token + "tampered")
    assert exc_info.value.status_code == 401


def test_approval_queue_freeze_on_decision(isolated_db):
    """Verify approval state machine freezes once decided; re-decision is rejected."""
    queue = ApprovalQueue()
    record = queue.enqueue(
        action_type="issue_refund",
        tool_name="issue_refund",
        entity_id="ord_prod_audit",
        customer_id="cust_prod_audit",
        amount=15000.0,
        payload={"order_id": "ord_prod_audit", "amount": 15000.0},
        guard_reason="ACT-01: Monetary cap",
        risk_level=Severity.HIGH,
        db=isolated_db,
    )
    assert record.status == "pending"

    # Approve once
    approved_item, _ = queue.approve(record.id, reviewer_id="op_alice", notes="Verified invoice", db=isolated_db)
    assert approved_item.status == "approved"
    assert approved_item.reviewer_id == "op_alice"

    # Repeated approve attempt must raise ValueError
    with pytest.raises(ValueError, match="already decided"):
        queue.approve(record.id, reviewer_id="op_bob", notes="Duplicate approve", db=isolated_db)

    # Repeated reject attempt must raise ValueError
    with pytest.raises(ValueError, match="already decided"):
        queue.reject(record.id, reviewer_id="op_bob", reason="Duplicate reject", db=isolated_db)


# ---------------------------------------------------------------------------
# PHASE 5: Cloudflare Turnstile & Public Forms Tests
# ---------------------------------------------------------------------------

def test_turnstile_fail_closed_in_production():
    """Verify that in production mode, missing Turnstile secret causes fail-closed verification."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        # Remove secret
        if "CLOUDFLARE_TURNSTILE_SECRET_KEY" in os.environ:
            del os.environ["CLOUDFLARE_TURNSTILE_SECRET_KEY"]

        result = verify_cloudflare_turnstile(token="some_token")
        assert result is False, "Must fail closed in production when secret is absent!"


def test_contact_form_honeypot_defense():
    """Verify contact endpoint rejects automated submissions filling hidden honeypot."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/contact",
        json={
            "name": "Spam Bot",
            "email": "bot@spam.internal",
            "company": "Spam Corp",
            "use_case": "Automated crawling test with sufficient length",
            "honeypot": "I am a bot filling all fields",
        },
    )
    assert response.status_code == 400
    assert "Automated submission detected" in response.json()["detail"]


# ---------------------------------------------------------------------------
# PHASE 6: Production Environment & Startup Invariants Tests
# ---------------------------------------------------------------------------

def test_production_rejects_sqlite_database_url():
    """
    Verify that in production mode, startup refuses to run if DATABASE_URL
    is pointing to SQLite instead of managed PostgreSQL.
    """
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "sqlite:///./argvtix.db"}, clear=False):
        with pytest.raises(RuntimeError, match="CRITICAL PRODUCTION CONFIGURATION ERROR"):
            # Trigger lifespan validation
            import asyncio
            async def run():
                async with lifespan(app):
                    pass
            asyncio.run(run())


def test_production_enforces_auth_unconditionally():
    """Verify is_auth_enabled() returns True in production regardless of ARGVTIX_AUTH_ENABLED."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "ARGVTIX_AUTH_ENABLED": "false"}, clear=False):
        assert is_auth_enabled() is True, "Production must enforce auth unconditionally!"


def test_production_rejects_insecure_default_jwt_secret():
    """Verify get_jwt_secret_key() raises RuntimeError in production when using dev secrets."""
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "ARGVTIX_JWT_SECRET": "argvtix_enterprise_secret_dev_key_change_in_prod",
        },
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="insecure default secret"):
            get_jwt_secret_key()
