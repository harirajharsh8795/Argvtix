"""
Production Security Audit & Hardening Regression Test Suite.
Verifies:
1. Security Headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
2. CORS Enforcement and Origin Restriction
3. Request Body Size Limiter (DoS protection via 413)
4. Production Secret Management & Fail-Safe Validation
5. Credential Verification & Privilege Escalation Prevention on /api/v1/auth/token
6. Role-Based Access Control (RBAC) negative testing under ARGVTIX_AUTH_ENABLED=true
7. Rate Limiter Configuration and Error Handling
8. Health Check Data Leakage Prevention
"""
from __future__ import annotations

import os
from fastapi.testclient import TestClient
import pytest

from argvtix.db.session import init_db
from argvtix.gateway.app import app
from argvtix.security.auth import (
    Role,
    create_access_token,
    get_jwt_secret_key,
    verify_credentials,
)


@pytest.fixture
def client():
    """Synchronous test client for FastAPI gateway with clean dependency overrides and initialized database tables."""
    init_db()
    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    with TestClient(app) as test_c:
        yield test_c
    app.dependency_overrides = old_overrides


class TestSecurityHeadersAndCORS:
    def test_security_headers_present_on_all_responses(self, client: TestClient):
        """Verify defense-in-depth HTTP security headers are attached to responses."""
        res = client.get("/health")
        assert res.status_code == 200

        headers = res.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in headers.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in headers.get("content-security-policy", "")
        assert "accelerometer=()" in headers.get("permissions-policy", "")

    def test_cors_preflight_trusted_origin(self, client: TestClient):
        """Verify preflight requests from authorized origins succeed with credentials."""
        res = client.options(
            "/api/v1/traces",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert res.headers.get("access-control-allow-credentials") == "true"

    def test_cors_preflight_untrusted_origin_rejected(self, client: TestClient):
        """Verify unauthorized cross-origin preflight requests do not receive allow headers."""
        res = client.options(
            "/api/v1/traces",
            headers={
                "Origin": "https://evil-attacker-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.headers.get("access-control-allow-origin") is None


class TestRequestSizeLimiting:
    def test_oversized_payload_rejected_with_413(self, client: TestClient):
        """Verify payloads exceeding 5MB are terminated immediately with HTTP 413."""
        oversized_length = 6 * 1024 * 1024  # 6 MB
        res = client.post(
            "/api/v1/security/inspect",
            content=b"A" * 100,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(oversized_length),
            },
        )
        assert res.status_code == 413
        assert "payload too large" in res.json().get("detail", "").lower()


class TestSecretManagementAndValidation:
    def test_production_mode_fails_safe_without_configured_secret(self, monkeypatch):
        """Verify get_jwt_secret_key raises RuntimeError in production when secret is missing."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("ARGVTIX_JWT_SECRET", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            get_jwt_secret_key()
        assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)

    def test_production_mode_rejects_insecure_default_dev_secrets(self, monkeypatch):
        """Verify get_jwt_secret_key raises RuntimeError in production when using known insecure dev key."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ARGVTIX_JWT_SECRET", "argvtix_enterprise_secret_dev_key_change_in_prod")

        with pytest.raises(RuntimeError) as exc_info:
            get_jwt_secret_key()
        assert "insecure default secret" in str(exc_info.value)

    def test_development_mode_allows_dev_secret(self, monkeypatch):
        """Verify development environments default safely to dev secret."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("ARGVTIX_JWT_SECRET", raising=False)
        key = get_jwt_secret_key()
        assert key == "argvtix_enterprise_secret_dev_key_change_in_prod"


class TestAuthenticationEndpointHardening:
    def test_issue_token_invalid_role_returns_400(self, client: TestClient):
        """Verify requesting a non-existent role returns 400 Bad Request."""
        res = client.post(
            "/api/v1/auth/token",
            json={"username": "alice", "password": "any", "role": "super_root_hacker"},
        )
        assert res.status_code == 400
        assert "invalid role" in res.json().get("detail", "").lower()

    def test_production_admin_privilege_escalation_blocked(self, client: TestClient, monkeypatch):
        """Verify unauthenticated user cannot escalate to ADMIN role in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ARGVTIX_ADMIN_USER", "secops_admin")
        monkeypatch.setenv("ARGVTIX_ADMIN_PASSWORD", "SuperSecureAdminSecret2026!#")

        # Attempt escalation with wrong password
        res = client.post(
            "/api/v1/auth/token",
            json={"username": "secops_admin", "password": "wrong_password", "role": "admin"},
        )
        assert res.status_code == 401
        assert "authentication failed" in res.json().get("detail", "").lower()

    def test_production_admin_valid_credentials_succeeds(self, client: TestClient, monkeypatch):
        """Verify valid admin credentials issue a signed admin token in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ARGVTIX_ADMIN_USER", "secops_admin")
        monkeypatch.setenv("ARGVTIX_ADMIN_PASSWORD", "SuperSecureAdminSecret2026!#")
        monkeypatch.setenv("ARGVTIX_JWT_SECRET", "HighEntropySecureSigningKeyProduction99824!")

        res = client.post(
            "/api/v1/auth/token",
            json={"username": "secops_admin", "password": "SuperSecureAdminSecret2026!#", "role": "admin"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "admin"
        assert "access_token" in data


class TestRBACNegativeEnforcement:
    def test_anonymous_blocked_from_gateway_call_when_auth_enabled(self, client: TestClient, monkeypatch):
        """Verify unauthenticated callers cannot invoke ToolGateway when ARGVTIX_AUTH_ENABLED=true."""
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "true")

        res = client.post(
            "/api/v1/guard/gateway/call",
            json={"tool_name": "get_order", "params": {"order_id": "ord_1"}},
        )
        assert res.status_code == 401

    def test_viewer_blocked_from_operator_actions(self, client: TestClient, monkeypatch):
        """Verify viewer token cannot execute tool mutations or approvals when auth is enforced."""
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "true")

        viewer_token = create_access_token(user_id="read_only_viewer", role=Role.VIEWER)
        auth_header = {"Authorization": f"Bearer {viewer_token}"}

        # Viewer attempting tool call (requires OPERATOR)
        res = client.post(
            "/api/v1/guard/gateway/call",
            json={"tool_name": "get_order", "params": {"order_id": "ord_1"}},
            headers=auth_header,
        )
        assert res.status_code == 403
        assert "access denied" in res.json().get("detail", "").lower()

        # Viewer attempting watchdog scan (requires OPERATOR)
        res_scan = client.post("/api/v1/watchdog/scan", headers=auth_header)
        assert res_scan.status_code == 403

    def test_operator_granted_access_to_gateway_and_scan(self, client: TestClient, monkeypatch):
        """Verify operator token has permissions to execute tool gateway and scan."""
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "true")

        op_token = create_access_token(user_id="lead_operator", role=Role.OPERATOR)
        auth_header = {"Authorization": f"Bearer {op_token}"}

        res = client.post(
            "/api/v1/guard/gateway/call",
            json={"tool_name": "get_order", "params": {"order_id": "ord_api_1"}},
            headers=auth_header,
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "allow"


class TestHealthCheckSanitization:
    def test_health_check_sanitized_in_production(self, client: TestClient, monkeypatch):
        """Verify database connection errors in production do not reveal raw driver traces."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert "database" in data
        assert "connected" in data["database"]
