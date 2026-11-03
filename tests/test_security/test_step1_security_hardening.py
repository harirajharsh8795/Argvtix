"""
Step 1 Security Hardening & Audit Verification Test Suite.

Verifies:
1. Tenant Isolation & Cross-Project Leak Prevention across Traces, Watchdog Findings, Approvals.
2. RBAC & Authentication gating on previously open endpoints (/evals/*, /security/*, /conflicts/*, /redteam/*, /cache/metrics).
3. AuthTokenRequest model hardening (no defaults, rejects empty payload with 422).
4. Dev-mode password rejection unless explicit opt-in flag ARGVTIX_ALLOW_INSECURE_DEV_AUTH is set.
5. Production startup configuration invariants (rejects SQLite, missing secret, or missing admin password).
"""

from __future__ import annotations

import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, WatchdogFindingRecord
from argvtix.db.session import get_db
from argvtix.gateway.app import app, verify_startup_configuration
from argvtix.guard.approvals import ApprovalQueue
from argvtix.security.auth import (
    Role,
    create_access_token,
    verify_credentials,
)


@pytest.fixture
def step1_db() -> Generator[Session, None, None]:
    """Isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(step1_db: Session) -> Generator[TestClient, None, None]:
    """TestClient wired to the isolated in-memory test database."""

    def _override_get_db():
        try:
            yield step1_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# 1. Tenant Isolation & Cross-Project Leak Prevention Tests
# ============================================================================


class TestTenantIsolation:
    """Verify strict tenant isolation across traces, watchdog, and approvals."""

    def test_trace_cross_project_isolation(self, client: TestClient, step1_db: Session) -> None:
        """Traces ingested for tenant A cannot be listed or read by tenant B."""
        token_a = create_access_token(
            user_id="user_a", project_id="tenant_alpha", role=Role.OPERATOR
        )
        token_b = create_access_token(
            user_id="user_b", project_id="tenant_beta", role=Role.OPERATOR
        )

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        trace_id_a = f"tr-{uuid.uuid4().hex[:12]}"
        trace_payload = {
            "trace_id": trace_id_a,
            "project_id": "tenant_alpha",
            "input_text": "Refund order 1042 for tenant alpha",
            "prompt_version": "v1",
            "model_version": "gemini-2.0-flash",
            "steps": [],
        }

        # Tenant A ingests trace
        res_ingest = client.post("/api/v1/traces", json=trace_payload, headers=headers_a)
        assert res_ingest.status_code == 201

        # Tenant A can list their trace
        res_list_a = client.get("/api/v1/traces", headers=headers_a)
        assert res_list_a.status_code == 200
        trace_ids_a = [t["trace_id"] for t in res_list_a.json()["items"]]
        assert trace_id_a in trace_ids_a

        # Tenant B cannot see Tenant A's trace in listing
        res_list_b = client.get("/api/v1/traces", headers=headers_b)
        assert res_list_b.status_code == 200
        trace_ids_b = [t["trace_id"] for t in res_list_b.json()["items"]]
        assert trace_id_a not in trace_ids_b

        # Tenant A can get trace by ID
        res_get_a = client.get(f"/api/v1/traces/{trace_id_a}", headers=headers_a)
        assert res_get_a.status_code == 200
        assert res_get_a.json()["trace_id"] == trace_id_a

        # Tenant B querying Tenant A's trace ID receives 404 (zero leakage)
        res_get_b = client.get(f"/api/v1/traces/{trace_id_a}", headers=headers_b)
        assert res_get_b.status_code == 404
        assert "not found" in res_get_b.json()["detail"].lower()

    def test_trace_stats_tenant_scoping(self, client: TestClient, step1_db: Session) -> None:
        """Trace summary statistics are strictly scoped to the querying tenant's project_id."""
        token_a = create_access_token(
            user_id="user_a", project_id="tenant_stats_a", role=Role.OPERATOR
        )
        token_b = create_access_token(
            user_id="user_b", project_id="tenant_stats_b", role=Role.OPERATOR
        )

        # Ingest 2 traces for Tenant A
        for i in range(2):
            client.post(
                "/api/v1/traces",
                json={
                    "trace_id": f"tr-stats-a-{i}-{uuid.uuid4().hex[:6]}",
                    "input_text": f"Query a {i}",
                    "prompt_version": "v1",
                    "model_version": "gemini-2.0-flash",
                    "steps": [],
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )

        # Ingest 1 trace for Tenant B
        client.post(
            "/api/v1/traces",
            json={
                "trace_id": f"tr-stats-b-{uuid.uuid4().hex[:6]}",
                "input_text": "Query b",
                "prompt_version": "v1",
                "model_version": "gemini-2.0-flash",
                "steps": [],
            },
            headers={"Authorization": f"Bearer {token_b}"},
        )

        stats_a = client.get(
            "/api/v1/traces/stats", headers={"Authorization": f"Bearer {token_a}"}
        ).json()
        stats_b = client.get(
            "/api/v1/traces/stats", headers={"Authorization": f"Bearer {token_b}"}
        ).json()

        assert stats_a["total_traces"] == 2
        assert stats_b["total_traces"] == 1

    def test_watchdog_findings_cross_project_isolation(
        self, client: TestClient, step1_db: Session
    ) -> None:
        """Watchdog findings are isolated per project; resolution by other tenant is rejected with 404."""
        token_a = create_access_token(
            user_id="op_a", project_id="proj_watchdog_a", role=Role.OPERATOR
        )
        token_b = create_access_token(
            user_id="op_b", project_id="proj_watchdog_b", role=Role.OPERATOR
        )

        # Create finding directly under proj_watchdog_a
        finding_a = WatchdogFindingRecord(
            project_id="proj_watchdog_a",
            rule_name="order_total_mismatch",
            severity="high",
            description="Total mismatch in order 555",
            entity_type="order",
            entity_id="ord_555",
            resolved=False,
        )
        step1_db.add(finding_a)
        step1_db.commit()
        step1_db.refresh(finding_a)

        # Tenant A lists findings -> sees the finding
        res_a = client.get(
            "/api/v1/watchdog/findings", headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_a.status_code == 200
        items_a = res_a.json()["items"]
        assert any(item["finding_id"] == finding_a.id for item in items_a)

        # Tenant B lists findings -> sees 0 findings
        res_b = client.get(
            "/api/v1/watchdog/findings", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_b.status_code == 200
        items_b = res_b.json()["items"]
        assert not any(item["finding_id"] == finding_a.id for item in items_b)

        # Tenant B attempts to resolve Tenant A's finding -> 404 Not Found
        res_resolve_b = client.patch(
            f"/api/v1/watchdog/findings/{finding_a.id}/resolve",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_resolve_b.status_code == 404

        # Tenant A resolves finding -> succeeds
        res_resolve_a = client.patch(
            f"/api/v1/watchdog/findings/{finding_a.id}/resolve",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_resolve_a.status_code == 200
        assert res_resolve_a.json()["status"] == "success"

    def test_guard_approvals_cross_project_isolation(
        self, client: TestClient, step1_db: Session
    ) -> None:
        """Approvals queued for Tenant A are inaccessible and cannot be approved/rejected by Tenant B."""
        token_a = create_access_token(user_id="op_a", project_id="proj_guard_a", role=Role.OPERATOR)
        token_b = create_access_token(user_id="op_b", project_id="proj_guard_b", role=Role.OPERATOR)

        queue = ApprovalQueue()
        record_a = queue.enqueue(
            action_type="issue_refund",
            tool_name="issue_refund",
            entity_id="order_999",
            payload={"order_id": "order_999", "amount": 6000.0},
            customer_id="cust_1",
            amount=6000.0,
            guard_reason="Amount exceeds policy limit",
            project_id="proj_guard_a",
            db=step1_db,
        )

        # Tenant A sees approval in list
        res_list_a = client.get(
            "/api/v1/guard/approvals", headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_list_a.status_code == 200
        appr_ids_a = [a["id"] for a in res_list_a.json()["approvals"]]
        assert record_a.id in appr_ids_a

        # Tenant B sees empty approval list
        res_list_b = client.get(
            "/api/v1/guard/approvals", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_list_b.status_code == 200
        appr_ids_b = [a["id"] for a in res_list_b.json()["approvals"]]
        assert record_a.id not in appr_ids_b

        # Tenant B cannot approve Tenant A's item -> 404
        res_appr_b = client.post(
            f"/api/v1/guard/approvals/{record_a.id}/approve",
            json={"reviewer_id": "malicious_reviewer", "notes": "unauthorized"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_appr_b.status_code == 404

        # Tenant B cannot reject Tenant A's item -> 404
        res_rej_b = client.post(
            f"/api/v1/guard/approvals/{record_a.id}/reject",
            json={"reviewer_id": "malicious_reviewer", "notes": "unauthorized"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_rej_b.status_code == 404

        # Tenant A rejects their approval -> 200
        res_rej_a = client.post(
            f"/api/v1/guard/approvals/{record_a.id}/reject",
            json={"reviewer_id": "valid_reviewer", "notes": "rejected correctly"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_rej_a.status_code == 200
        assert res_rej_a.json()["approval_status"] == "rejected"


# ============================================================================
# 2. Authentication & Role Checks on All Open Endpoints
# ============================================================================


class TestOpenEndpointsHardening:
    """Verify all previously open endpoints require authentication and appropriate roles."""

    def test_anonymous_rejected_on_all_hardened_endpoints(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When auth is enabled, unauthenticated requests to protected endpoints return 401."""
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "true")

        open_endpoints = [
            ("GET", "/api/v1/cache/metrics", None),
            ("GET", "/api/v1/evals/planted-scenarios", None),
            ("POST", "/api/v1/evals/verify-claims", {"agent_response": "Test", "tool_records": []}),
            ("POST", "/api/v1/security/mask", {"text": "Call 9876543210"}),
            ("POST", "/api/v1/security/inspect", {"text": "System prompt info"}),
            ("POST", "/api/v1/conflicts/scan", {}),
            ("POST", "/api/v1/security/conflicts/scan", {}),
            ("POST", "/api/v1/redteam/run", {}),
            ("POST", "/api/v1/security/redteam/run", {}),
            ("POST", "/api/v1/evals/passk", {"k": 2}),
        ]

        for method, endpoint, payload in open_endpoints:
            if method == "GET":
                res = client.get(endpoint)
            else:
                res = client.post(endpoint, json=payload or {})
            assert res.status_code == 401, f"Endpoint {endpoint} allowed anonymous access!"
            assert "detail" in res.json()

    def test_viewer_role_blocked_from_operator_actions(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Viewer role can access read-only endpoints but is blocked (403) from operator endpoints."""
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "true")
        token_viewer = create_access_token(user_id="viewer_user", role=Role.VIEWER)
        headers = {"Authorization": f"Bearer {token_viewer}"}

        # Viewer can read cache metrics and planted scenarios
        res_cache = client.get("/api/v1/cache/metrics", headers=headers)
        assert res_cache.status_code == 200

        res_scenarios = client.get("/api/v1/evals/planted-scenarios", headers=headers)
        assert res_scenarios.status_code == 200

        # Viewer is forbidden from operator endpoints
        operator_endpoints = [
            ("/api/v1/evals/verify-claims", {"agent_response": "Test", "tool_records": []}),
            ("/api/v1/security/mask", {"text": "Aadhaar 1234-5678-9012"}),
            ("/api/v1/security/inspect", {"text": "Outbound text"}),
            ("/api/v1/conflicts/scan", {}),
            ("/api/v1/security/conflicts/scan", {}),
            ("/api/v1/redteam/run", {}),
            ("/api/v1/security/redteam/run", {}),
            ("/api/v1/evals/passk", {"k": 2}),
        ]

        for endpoint, payload in operator_endpoints:
            res = client.post(endpoint, json=payload, headers=headers)
            assert res.status_code == 403, f"Endpoint {endpoint} allowed viewer role!"

    def test_operator_granted_access_to_hardened_endpoints(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Operator role is permitted to execute operator endpoints."""
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "true")
        token_operator = create_access_token(user_id="op_user", role=Role.OPERATOR)
        headers = {"Authorization": f"Bearer {token_operator}"}

        # Mask PII endpoint
        res_mask = client.post(
            "/api/v1/security/mask", json={"text": "Phone: 9876543210"}, headers=headers
        )
        assert res_mask.status_code == 200
        assert res_mask.json()["has_pii"] is True

        # Inspect outbound text endpoint
        res_inspect = client.post(
            "/api/v1/security/inspect", json={"text": "Safe message"}, headers=headers
        )
        assert res_inspect.status_code == 200
        assert res_inspect.json()["is_safe"] is True

        # Verify claims endpoint
        res_claims = client.post(
            "/api/v1/evals/verify-claims",
            json={"agent_response": "Refund processed.", "tool_records": []},
            headers=headers,
        )
        assert res_claims.status_code == 200


# ============================================================================
# 3. Token Model & Dev Mode Hardening Tests
# ============================================================================


class TestTokenModelAndDevModeHardening:
    """Verify AuthTokenRequest defaults are removed and dev-mode password validation is strict."""

    def test_token_request_rejects_empty_payload(self, client: TestClient) -> None:
        """AuthTokenRequest has no admin/admin defaults; empty JSON is rejected with 422."""
        res = client.post("/api/v1/auth/token", json={})
        assert res.status_code == 422
        errors = res.json()["detail"]
        missing_fields = {e["loc"][-1] for e in errors if e["type"] == "missing"}
        assert "username" in missing_fields
        assert "password" in missing_fields

    def test_dev_mode_rejects_blind_passwords_without_opt_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In development mode, arbitrary passwords fail unless ARGVTIX_ALLOW_INSECURE_DEV_AUTH is set."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ARGVTIX_ALLOW_INSECURE_DEV_AUTH", "false")
        monkeypatch.setenv("ARGVTIX_ADMIN_PASSWORD", "SuperSecurePassword123!")

        # Random password fails
        is_valid, role, reason = verify_credentials("admin", "wrong_random_pass", Role.ADMIN)
        assert is_valid is False
        assert "Blind password acceptance is disabled" in reason

        # Correct configured password succeeds
        is_valid_ok, role_ok, _ = verify_credentials("admin", "SuperSecurePassword123!", Role.ADMIN)
        assert is_valid_ok is True
        assert role_ok == Role.ADMIN

    def test_dev_mode_opt_in_allows_development_bypass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ARGVTIX_ALLOW_INSECURE_DEV_AUTH=true, dev mode accepts arbitrary test credentials."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ARGVTIX_ALLOW_INSECURE_DEV_AUTH", "true")

        is_valid, role, reason = verify_credentials("any_dev_user", "any_pass", Role.OPERATOR)
        assert is_valid is True
        assert role == Role.OPERATOR
        assert "Development mode opt-in" in reason


# ============================================================================
# 4. Configuration Naming & Startup Invariants Tests
# ============================================================================


class TestConfigurationAndStartupInvariants:
    """Verify startup validation fails when required production variables are missing or insecure."""

    def test_startup_fails_in_production_with_sqlite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Production startup fails if DATABASE_URL is SQLite."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr("argvtix.db.session.DATABASE_URL", "sqlite:///./prod_test.db")

        with pytest.raises(RuntimeError) as exc_info:
            verify_startup_configuration()
        assert "pointing to SQLite" in str(exc_info.value)

    def test_startup_fails_in_production_without_admin_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production startup fails if ARGVTIX_ADMIN_PASSWORD is empty."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(
            "argvtix.db.session.DATABASE_URL", "postgresql://user:pass@host:5432/db"
        )
        monkeypatch.setenv(
            "ARGVTIX_JWT_SECRET", "super_high_entropy_prod_secret_key_32_bytes_long_123"
        )
        monkeypatch.delenv("ARGVTIX_ADMIN_PASSWORD", raising=False)
        monkeypatch.delenv("PROOFLINE_ADMIN_PASSWORD", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            verify_startup_configuration()
        assert "ARGVTIX_ADMIN_PASSWORD is not configured" in str(exc_info.value)

    def test_startup_succeeds_in_production_with_valid_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production startup succeeds when all required production variables are properly configured."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(
            "argvtix.db.session.DATABASE_URL", "postgresql://user:pass@host:5432/db"
        )
        monkeypatch.setenv(
            "ARGVTIX_JWT_SECRET", "super_high_entropy_prod_secret_key_32_bytes_long_123"
        )
        monkeypatch.setenv("ARGVTIX_ADMIN_PASSWORD", "EnterpriseAdminSecretPass987!")

        # Should complete without raising any exception
        verify_startup_configuration()

    def test_legacy_proofline_alias_compatibility(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy PROOFLINE_* environment variables continue to work as aliases."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(
            "argvtix.db.session.DATABASE_URL", "postgresql://user:pass@host:5432/db"
        )
        monkeypatch.delenv("ARGVTIX_JWT_SECRET", raising=False)
        monkeypatch.delenv("ARGVTIX_ADMIN_PASSWORD", raising=False)
        monkeypatch.setenv(
            "PROOFLINE_JWT_SECRET", "legacy_high_entropy_secret_at_least_32_bytes_long"
        )
        monkeypatch.setenv("PROOFLINE_ADMIN_PASSWORD", "LegacyAdminPass123!")

        # Resolves aliases without raising exception
        verify_startup_configuration()
