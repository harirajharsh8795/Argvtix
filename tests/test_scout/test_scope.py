"""Tests for Argvtix Scout permission, scope, and signature verification."""

from datetime import UTC, datetime, timedelta

import pytest

from argvtix.scout.scope import (
    InvalidSignatureError,
    MissingAuthorizationError,
    ScopeConfig,
    ScopeExpiredError,
    TargetHostNotAllowedError,
    TargetPathNotAllowedError,
    TargetTier,
    compute_scope_signature,
    load_scope_from_yaml,
    validate_scope_allows_request,
    verify_scope_signature,
)


@pytest.fixture
def valid_sandbox_scope() -> ScopeConfig:
    now = datetime.now(UTC)
    return ScopeConfig(
        scope_id="SCOPE-TEST-001",
        project_id="test-proj",
        target_name="Test Sandbox Bot",
        target_url="http://localhost:8000/api/chat",
        target_tier=TargetTier.T0_INTERNAL_SANDBOX,
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=24),
        allowed_hosts=["localhost", "127.0.0.1"],
        allowed_paths=["/api/chat"],
        max_rpm=60,
    )


class TestScopeVerification:
    def test_valid_sandbox_scope_passes(self, valid_sandbox_scope: ScopeConfig):
        # Should not raise any exception
        validate_scope_allows_request(valid_sandbox_scope, "http://localhost:8000/api/chat")

    def test_expired_scope_raises_error(self, valid_sandbox_scope: ScopeConfig):
        now = datetime.now(UTC)
        valid_sandbox_scope.valid_until = now - timedelta(minutes=5)
        with pytest.raises(ScopeExpiredError, match="is not active"):
            validate_scope_allows_request(valid_sandbox_scope, "http://localhost:8000/api/chat")

    def test_future_scope_not_yet_active(self, valid_sandbox_scope: ScopeConfig):
        now = datetime.now(UTC)
        valid_sandbox_scope.valid_from = now + timedelta(hours=2)
        with pytest.raises(ScopeExpiredError, match="is not active"):
            validate_scope_allows_request(valid_sandbox_scope, "http://localhost:8000/api/chat")

    def test_unauthorized_host_raises_error(self, valid_sandbox_scope: ScopeConfig):
        with pytest.raises(TargetHostNotAllowedError, match="not in allowed_hosts"):
            validate_scope_allows_request(
                valid_sandbox_scope, "http://malicious-external-target.com/api/chat"
            )

    def test_unauthorized_path_raises_error(self, valid_sandbox_scope: ScopeConfig):
        with pytest.raises(TargetPathNotAllowedError, match="allowed_paths"):
            validate_scope_allows_request(
                valid_sandbox_scope, "http://localhost:8000/admin/secrets"
            )

    def test_client_tier_requires_written_auth_and_email(self, valid_sandbox_scope: ScopeConfig):
        valid_sandbox_scope.target_tier = TargetTier.T2_CLIENT_PRODUCTION
        valid_sandbox_scope.written_authorization_id = ""
        with pytest.raises(MissingAuthorizationError, match="written_authorization_id"):
            validate_scope_allows_request(valid_sandbox_scope, "http://localhost:8000/api/chat")

        valid_sandbox_scope.written_authorization_id = "AUTH-2026-CLIENT-01"
        valid_sandbox_scope.signoff_contact_email = "invalid-email"
        with pytest.raises(MissingAuthorizationError, match="signoff_contact_email"):
            validate_scope_allows_request(valid_sandbox_scope, "http://localhost:8000/api/chat")

        valid_sandbox_scope.signoff_contact_email = "ciso@client.com"
        # Now it passes
        validate_scope_allows_request(valid_sandbox_scope, "http://localhost:8000/api/chat")

    def test_cryptographic_signature_verification(self, valid_sandbox_scope: ScopeConfig):
        secret = "super-secret-hmac-key"
        sig = compute_scope_signature(valid_sandbox_scope, secret)
        assert len(sig) == 64

        valid_sandbox_scope.signature = sig
        assert verify_scope_signature(valid_sandbox_scope, secret) is True

        # Tampering with target_url fails signature
        valid_sandbox_scope.target_url = "http://localhost:8000/tampered"
        assert verify_scope_signature(valid_sandbox_scope, secret) is False

    def test_load_scope_from_yaml_with_signature_enforcement(
        self, valid_sandbox_scope: ScopeConfig
    ):
        secret = "argvtix-secret-key"
        valid_sandbox_scope.signature = compute_scope_signature(valid_sandbox_scope, secret)
        raw_dict = valid_sandbox_scope.model_dump()
        raw_dict["valid_from"] = raw_dict["valid_from"].isoformat()
        raw_dict["valid_until"] = raw_dict["valid_until"].isoformat()

        loaded = load_scope_from_yaml(raw_dict, secret_key=secret, enforce_signature=True)
        assert loaded.scope_id == valid_sandbox_scope.scope_id

        # Invalid secret key raises InvalidSignatureError
        with pytest.raises(InvalidSignatureError):
            load_scope_from_yaml(raw_dict, secret_key="wrong-key", enforce_signature=True)
