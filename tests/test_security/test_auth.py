"""
Tests for JWT Authentication, RBAC Roles, and Project Scoping.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from argvtix.security.auth import (
    Role,
    TokenPayload,
    create_access_token,
    get_current_user,
    require_role,
    verify_access_token,
)


class TestJWTTokenOperations:
    def test_create_and_verify_token_roundtrip(self):
        token = create_access_token(
            user_id="user_test_01",
            project_id="proj_ecommerce",
            role=Role.ADMIN,
            expires_delta=timedelta(minutes=30),
        )
        assert isinstance(token, str)

        payload: TokenPayload = verify_access_token(token)
        assert payload.sub == "user_test_01"
        assert payload.project_id == "proj_ecommerce"
        assert payload.role == Role.ADMIN
        assert payload.exp > 0

    def test_expired_token_raises_401(self):
        # Create token that already expired 10 minutes ago
        token = create_access_token(
            user_id="user_expired",
            expires_delta=timedelta(minutes=-10),
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_access_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_invalid_signature_raises_401(self):
        token = create_access_token(user_id="user_good")
        tampered_token = token + "xyz"
        with pytest.raises(HTTPException) as exc_info:
            verify_access_token(tampered_token)
        assert exc_info.value.status_code == 401


class TestRBACPermissions:
    def test_admin_has_access_to_all_roles(self):
        admin_user = TokenPayload(sub="admin_1", project_id="p1", role=Role.ADMIN, exp=9999999999)

        # Admin can access viewer, operator, admin endpoints
        assert require_role(Role.VIEWER)(admin_user) == admin_user
        assert require_role(Role.OPERATOR)(admin_user) == admin_user
        assert require_role(Role.ADMIN)(admin_user) == admin_user

    def test_operator_has_access_to_viewer_and_operator(self):
        op_user = TokenPayload(sub="op_1", project_id="p1", role=Role.OPERATOR, exp=9999999999)

        assert require_role(Role.VIEWER)(op_user) == op_user
        assert require_role(Role.OPERATOR)(op_user) == op_user

        with pytest.raises(HTTPException) as exc_info:
            require_role(Role.ADMIN)(op_user)
        assert exc_info.value.status_code == 403

    def test_viewer_is_restricted_from_operator_and_admin(self):
        viewer_user = TokenPayload(sub="view_1", project_id="p1", role=Role.VIEWER, exp=9999999999)

        assert require_role(Role.VIEWER)(viewer_user) == viewer_user

        with pytest.raises(HTTPException) as exc_info:
            require_role(Role.OPERATOR)(viewer_user)
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as exc_info:
            require_role(Role.ADMIN)(viewer_user)
        assert exc_info.value.status_code == 403


class TestAuthMiddlewareGating:
    def test_dev_mode_auto_injects_credentials(self, monkeypatch):
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "false")
        user = get_current_user(auth=None)
        assert user.sub == "dev_admin"
        assert user.role == Role.ADMIN
        assert user.project_id == "default"

    def test_production_mode_requires_bearer_token(self, monkeypatch):
        monkeypatch.setenv("ARGVTIX_AUTH_ENABLED", "true")

        # Missing token raises 401
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(auth=None)
        assert exc_info.value.status_code == 401

        # Valid token succeeds
        token = create_access_token(user_id="prod_user", role=Role.OPERATOR)
        auth_cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = get_current_user(auth=auth_cred)
        assert user.sub == "prod_user"
        assert user.role == Role.OPERATOR
