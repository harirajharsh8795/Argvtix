"""
Authentication & Role-Based Access Control (RBAC) Module.

Provides JWT token issuance, verification, and multi-tenant project scoping:
- Roles: ADMIN > OPERATOR > VIEWER
- Gated by ARGVTIX_AUTH_ENABLED (defaults to false for dev ease)
- Multi-tenancy: Scopes all queries by project_id
"""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

INSECURE_DEV_SECRETS: set[str] = {
    "argvtix_enterprise_secret_dev_key_change_in_prod",
    "prod_super_secret_jwt_key_2026",
    "secret",
    "change_me",
    "default",
    "admin",
}

DEFAULT_DEV_SECRET = "argvtix_enterprise_secret_dev_key_change_in_prod"


def get_jwt_secret_key() -> str:
    """Safely retrieves the JWT signing key with production guardrails.

    In production environments, rejects insecure fallback defaults.
    """
    secret = os.getenv("ARGVTIX_JWT_SECRET", os.getenv("PROOFLINE_JWT_SECRET", "")).strip()
    env = os.getenv("ENVIRONMENT", os.getenv("ARGVTIX_ENV", "development")).lower()
    is_prod = env in ("production", "prod", "staging")

    if not secret:
        if is_prod:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: ARGVTIX_JWT_SECRET environment variable "
                "must be explicitly configured with a high-entropy secret in production."
            )
        return DEFAULT_DEV_SECRET

    if is_prod and secret in INSECURE_DEV_SECRETS:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: ARGVTIX_JWT_SECRET is using a known insecure "
            "default secret. You must configure a high-entropy production signing key."
        )

    return secret


JWT_SECRET_KEY = os.getenv(
    "ARGVTIX_JWT_SECRET", os.getenv("PROOFLINE_JWT_SECRET", DEFAULT_DEV_SECRET)
)
JWT_ALGORITHM = "HS256"
DEFAULT_EXPIRATION_HOURS = 24

security_scheme = HTTPBearer(auto_error=False)


class Role(str, Enum):
    """User authorization roles."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


ROLE_HIERARCHY: dict[Role, int] = {
    Role.ADMIN: 3,
    Role.OPERATOR: 2,
    Role.VIEWER: 1,
}


class TokenPayload(BaseModel):
    """Standardized claims contained within Argvtix JWT tokens."""

    sub: str = Field(..., description="User ID / Subject")
    project_id: str = Field(default="default", description="Scoped enterprise project ID")
    role: Role = Field(default=Role.VIEWER, description="Assigned RBAC role")
    exp: int = Field(..., description="UNIX timestamp expiration")


def is_auth_enabled() -> bool:
    """Returns True if production JWT authentication is enforced."""
    env = os.getenv("ENVIRONMENT", os.getenv("ARGVTIX_ENV", "development")).lower()
    if env in ("production", "prod", "staging"):
        return True
    return os.getenv(
        "ARGVTIX_AUTH_ENABLED", os.getenv("PROOFLINE_AUTH_ENABLED", "false")
    ).lower() in (
        "true",
        "1",
        "yes",
    )


def verify_credentials(
    username: str,
    password: str,
    requested_role: Role = Role.VIEWER,
) -> tuple[bool, Role, str]:
    """Constant-time credential verification and role privilege safety checks.

    Returns (is_valid, granted_role, reason).
    """
    if not username or not password:
        return False, Role.VIEWER, "Username and password are required"

    env = os.getenv("ENVIRONMENT", os.getenv("ARGVTIX_ENV", "development")).lower()
    is_prod = env in ("production", "prod", "staging")

    configured_admin_user = os.getenv(
        "ARGVTIX_ADMIN_USER", os.getenv("PROOFLINE_ADMIN_USER", "admin")
    )
    configured_admin_password = os.getenv(
        "ARGVTIX_ADMIN_PASSWORD", os.getenv("PROOFLINE_ADMIN_PASSWORD", "")
    )
    configured_op_pass = os.getenv(
        "ARGVTIX_OPERATOR_PASSWORD", os.getenv("PROOFLINE_OPERATOR_PASSWORD", "otp_verified")
    )
    configured_viewer_pass = os.getenv(
        "ARGVTIX_VIEWER_PASSWORD", os.getenv("PROOFLINE_VIEWER_PASSWORD", "")
    )
    configured_dev_pass = os.getenv("ARGVTIX_DEV_PASSWORD", os.getenv("PROOFLINE_DEV_PASSWORD", ""))

    # If in dev / test mode (not production)
    if not is_prod:
        allow_insecure_dev = os.getenv(
            "ARGVTIX_ALLOW_INSECURE_DEV_AUTH",
            os.getenv("PROOFLINE_ALLOW_INSECURE_DEV_AUTH", "false"),
        ).lower() in ("true", "1", "yes")

        if allow_insecure_dev:
            return (
                True,
                requested_role,
                f"Authenticated as {requested_role.value} (Development mode opt-in)",
            )

        # When insecure dev bypass is not opted into, verify credentials against configured values
        is_admin_user = secrets.compare_digest(username.strip(), configured_admin_user)
        if (
            configured_admin_password
            and is_admin_user
            and secrets.compare_digest(password.strip(), configured_admin_password)
        ):
            return True, requested_role, f"Authenticated as {requested_role.value}"
        if configured_dev_pass and secrets.compare_digest(password.strip(), configured_dev_pass):
            return True, requested_role, f"Authenticated as {requested_role.value}"
        if configured_op_pass and secrets.compare_digest(password.strip(), configured_op_pass):
            return (
                True,
                Role.OPERATOR if requested_role in (Role.OPERATOR, Role.VIEWER) else Role.VIEWER,
                "Authenticated as Operator",
            )
        if configured_viewer_pass and secrets.compare_digest(
            password.strip(), configured_viewer_pass
        ):
            return True, Role.VIEWER, "Authenticated as Viewer"

        return (
            False,
            Role.VIEWER,
            "Invalid credentials. Blind password acceptance is disabled in development mode. "
            "Configure ARGVTIX_ADMIN_PASSWORD / ARGVTIX_DEV_PASSWORD or explicitly set ARGVTIX_ALLOW_INSECURE_DEV_AUTH=true.",
        )

    # Production Strict Mode: Validate credentials against environment
    if not configured_admin_password:
        return False, Role.VIEWER, "Administrative authentication is not configured in production"

    is_admin_user = secrets.compare_digest(username.strip(), configured_admin_user)
    is_admin_pass = secrets.compare_digest(password.strip(), configured_admin_password)

    if requested_role == Role.ADMIN:
        if is_admin_user and is_admin_pass:
            return True, Role.ADMIN, "Authenticated as Admin"
        return False, Role.VIEWER, "Invalid administrative credentials"

    # Operator role (Enterprise Engineer or Ops)
    if requested_role == Role.OPERATOR:
        if is_admin_user and is_admin_pass:
            return True, Role.OPERATOR, "Authenticated as Operator (Admin tier)"
        if configured_op_pass and secrets.compare_digest(password.strip(), configured_op_pass):
            return True, Role.OPERATOR, "Authenticated as Operator"
        return False, Role.VIEWER, "Invalid operator credentials"

    # Viewer role
    if is_admin_user and is_admin_pass:
        return True, Role.VIEWER, "Authenticated as Viewer"
    if configured_viewer_pass and secrets.compare_digest(password.strip(), configured_viewer_pass):
        return True, Role.VIEWER, "Authenticated as Viewer"

    return False, Role.VIEWER, "Invalid credentials"


def create_access_token(
    user_id: str | dict[str, Any],
    project_id: str = "default",
    role: Role = Role.VIEWER,
    expires_delta: timedelta | None = None,
    secret_key: str | None = None,
) -> str:
    """Generates a signed HS256 JWT access token.

    Supports both argument parameters and dictionary payload conventions.
    """
    if isinstance(user_id, dict):
        d = user_id
        actual_user_id = str(d.get("sub", d.get("user_id", "admin")))
        actual_project_id = str(d.get("project_id", project_id))
        r_val = d.get("role", role)
        if isinstance(r_val, Role):
            actual_role = r_val
        elif isinstance(r_val, str):
            try:
                actual_role = Role(r_val.lower())
            except ValueError:
                actual_role = Role.VIEWER
        else:
            actual_role = Role.VIEWER
        user_id = actual_user_id
        project_id = actual_project_id
        role = actual_role

    key = secret_key or get_jwt_secret_key()
    delta = expires_delta or timedelta(hours=DEFAULT_EXPIRATION_HOURS)
    expire_dt = datetime.now(UTC) + delta
    payload = {
        "sub": user_id,
        "project_id": project_id,
        "role": role.value,
        "exp": int(expire_dt.timestamp()),
    }
    return jwt.encode(payload, key, algorithm=JWT_ALGORITHM)


def verify_access_token(
    token: str,
    secret_key: str | None = None,
) -> TokenPayload:
    """Decodes and validates a JWT token."""
    key = secret_key or get_jwt_secret_key()
    try:
        decoded = jwt.decode(token, key, algorithms=[JWT_ALGORITHM])
        return TokenPayload(
            sub=decoded["sub"],
            project_id=decoded.get("project_id", "default"),
            role=Role(decoded.get("role", "viewer")),
            exp=decoded["exp"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)] = None,
) -> TokenPayload:
    """FastAPI dependency extracting and verifying the authenticated user.

    If Bearer credentials are provided, validates and returns the token payload.
    If credentials are not provided and ARGVTIX_AUTH_ENABLED is false, injects default dev credentials.
    If ARGVTIX_AUTH_ENABLED is true and credentials are missing or invalid, raises 401.
    """
    if auth and auth.credentials:
        return verify_access_token(auth.credentials)

    if not is_auth_enabled():
        return TokenPayload(
            sub="dev_admin",
            project_id="default",
            role=Role.ADMIN,
            exp=int((datetime.now(UTC) + timedelta(days=365)).timestamp()),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authorization header missing or invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(min_role: Role):
    """Factory creating a FastAPI dependency enforcing minimum RBAC permissions."""

    def _role_checker(user: Annotated[TokenPayload, Depends(get_current_user)]) -> TokenPayload:
        user_rank = ROLE_HIERARCHY.get(user.role, 0)
        required_rank = ROLE_HIERARCHY.get(min_role, 99)

        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Required role '{min_role.value}' or higher, but got '{user.role.value}'",
            )
        return user

    return _role_checker
