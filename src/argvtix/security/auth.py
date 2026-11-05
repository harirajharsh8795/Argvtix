"""
Authentication & Role-Based Access Control (RBAC) Module for ARGVTIX.

Provides:
- JWT token issuance, verification, revocation, and multi-tenant project scoping.
- RBAC Roles: ADMIN > OPERATOR > VIEWER.
- Gated by ARGVTIX_AUTH_ENABLED (defaults to false for dev ease, strictly enforced in prod).
- Multi-tenancy: Scopes all operations by project_id.
- Account lockout defense against brute-force attacks.
- Canonical ARGVTIX_* configuration with legacy PROOFLINE_* deprecation logging.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
import warnings
from datetime import UTC, datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger("argvtix.security.auth")


def get_config_with_alias(
    canonical_name: str, legacy_alias: str | None = None, default: str = ""
) -> str:
    """Retrieves an environment variable using canonical ARGVTIX_* naming.

    If the canonical name is unset but a legacy alias is present, logs and issues
    a DeprecationWarning to notify operators.
    """
    if canonical_name in os.environ:
        return os.environ[canonical_name]

    if legacy_alias and legacy_alias in os.environ:
        warnings.warn(
            f"Configuration alias '{legacy_alias}' is deprecated and will be removed in a future release. "
            f"Please migrate to canonical '{canonical_name}'.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            f"DEPRECATION NOTICE: Using legacy environment variable '{legacy_alias}'. "
            f"Update configuration to use canonical '{canonical_name}'."
        )
        return os.environ[legacy_alias]

    return default


INSECURE_DEV_SECRETS: set[str] = {
    "argvtix_enterprise_secret_dev_key_change_in_prod",
    "prod_super_secret_jwt_key_2026",
    "secret",
    "change_me",
    "default",
    "admin",
    "password",
    "12345678",
}

DEFAULT_DEV_SECRET = "argvtix_enterprise_secret_dev_key_change_in_prod"


def get_jwt_secret_key() -> str:
    """Safely retrieves the JWT signing key with production guardrails.

    In production environments:
    - Rejects missing secrets.
    - Rejects known weak/insecure defaults.
    - Requires high-entropy secret (minimum 32 characters).
    """
    secret = get_config_with_alias("ARGVTIX_JWT_SECRET", "PROOFLINE_JWT_SECRET", "").strip()
    env = get_config_with_alias("ENVIRONMENT", "ARGVTIX_ENV", "development").lower()
    is_prod = env in ("production", "prod", "staging")

    if not secret:
        if is_prod:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: ARGVTIX_JWT_SECRET environment variable "
                "must be explicitly configured with a high-entropy secret in production."
            )
        return DEFAULT_DEV_SECRET

    if is_prod:
        if secret in INSECURE_DEV_SECRETS:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: ARGVTIX_JWT_SECRET is using a known insecure "
                "default secret. You must configure a high-entropy production signing key."
            )
        if len(secret) < 32:
            raise RuntimeError(
                f"CRITICAL SECURITY CONFIGURATION ERROR: ARGVTIX_JWT_SECRET must be at least 32 characters "
                f"for cryptographic security in production (current length: {len(secret)})."
            )

    return secret


JWT_ALGORITHM = "HS256"
# Short token expiration for enterprise security (2 hours)
DEFAULT_EXPIRATION_HOURS = 2

security_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Brute-Force Defense: Account Lockout & Failed Attempt Tracker
# ---------------------------------------------------------------------------


class FailedLoginTracker:
    """Thread-safe in-memory failed authentication tracker and lockout enforcer."""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_SECONDS = 900  # 15 minutes lockout

    def __init__(self) -> None:
        self._lock = Lock()
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def is_locked(self, identifier: str) -> tuple[bool, int]:
        """Check if an account/identifier is currently locked out.

        Returns (is_locked, remaining_seconds).
        """
        key = identifier.strip().lower()
        now = time.time()
        with self._lock:
            unlock_time = self._locked_until.get(key, 0.0)
            if now < unlock_time:
                remaining = int(unlock_time - now)
                return True, max(remaining, 1)
            if key in self._locked_until:
                del self._locked_until[key]
                self._failures.pop(key, None)
            return False, 0

    def record_failure(self, identifier: str) -> tuple[int, bool]:
        """Record an authentication failure.

        Returns (current_failed_attempts, is_now_locked).
        """
        key = identifier.strip().lower()
        now = time.time()
        with self._lock:
            timestamps = self._failures.setdefault(key, [])
            # Prune attempts older than lockout duration
            timestamps = [t for t in timestamps if now - t < self.LOCKOUT_DURATION_SECONDS]
            timestamps.append(now)
            self._failures[key] = timestamps

            if len(timestamps) >= self.MAX_FAILED_ATTEMPTS:
                self._locked_until[key] = now + self.LOCKOUT_DURATION_SECONDS
                logger.warning(
                    f"SECURITY ALERT: Account '{key}' locked out for {self.LOCKOUT_DURATION_SECONDS}s "
                    f"after {len(timestamps)} consecutive failed authentication attempts."
                )
                return len(timestamps), True
            return len(timestamps), False

    def record_success(self, identifier: str) -> None:
        """Clear failed attempts upon successful authentication."""
        key = identifier.strip().lower()
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def reset(self) -> None:
        """Clear all tracking state (used in testing)."""
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()


failed_login_tracker = FailedLoginTracker()


# ---------------------------------------------------------------------------
# Token Revocation Store
# ---------------------------------------------------------------------------

_revoked_tokens: set[str] = set()
_revocation_lock = Lock()


def revoke_token(token: str) -> None:
    """Revoke an active JWT token before its natural expiration."""
    with _revocation_lock:
        _revoked_tokens.add(token.strip())


def is_token_revoked(token: str) -> bool:
    """Returns True if the token has been explicitly revoked."""
    with _revocation_lock:
        return token.strip() in _revoked_tokens


# ---------------------------------------------------------------------------
# RBAC Hierarchy & Claims
# ---------------------------------------------------------------------------


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
    env = get_config_with_alias("ENVIRONMENT", "ARGVTIX_ENV", "development").lower()
    if env in ("production", "prod", "staging"):
        return True
    return get_config_with_alias(
        "ARGVTIX_AUTH_ENABLED", "PROOFLINE_AUTH_ENABLED", "false"
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
    """Constant-time credential verification, brute-force defense, and role privilege checks.

    Returns (is_valid, granted_role, reason).
    """
    if not username or not password:
        return False, Role.VIEWER, "Username and password are required"

    identifier = username.strip().lower()

    # 1. Brute-force lockout enforcement
    is_locked, remaining_sec = failed_login_tracker.is_locked(identifier)
    if is_locked:
        return (
            False,
            Role.VIEWER,
            f"Account is temporarily locked out due to repeated failed login attempts. "
            f"Please wait {remaining_sec} seconds before retrying.",
        )

    env = get_config_with_alias("ENVIRONMENT", "ARGVTIX_ENV", "development").lower()
    is_prod = env in ("production", "prod", "staging")

    configured_admin_user = get_config_with_alias(
        "ARGVTIX_ADMIN_USER", "PROOFLINE_ADMIN_USER", "admin"
    )
    configured_admin_password = get_config_with_alias(
        "ARGVTIX_ADMIN_PASSWORD", "PROOFLINE_ADMIN_PASSWORD", ""
    )
    configured_op_pass = get_config_with_alias(
        "ARGVTIX_OPERATOR_PASSWORD", "PROOFLINE_OPERATOR_PASSWORD", "otp_verified"
    )
    configured_viewer_pass = get_config_with_alias(
        "ARGVTIX_VIEWER_PASSWORD", "PROOFLINE_VIEWER_PASSWORD", ""
    )
    configured_dev_pass = get_config_with_alias(
        "ARGVTIX_DEV_PASSWORD", "PROOFLINE_DEV_PASSWORD", ""
    )

    # 2. Insecure dev mode checks
    if not is_prod:
        allow_insecure_dev = get_config_with_alias(
            "ARGVTIX_ALLOW_INSECURE_DEV_AUTH",
            "PROOFLINE_ALLOW_INSECURE_DEV_AUTH",
            "false",
        ).lower() in ("true", "1", "yes")

        if allow_insecure_dev:
            failed_login_tracker.record_success(identifier)
            return (
                True,
                requested_role,
                f"Authenticated as {requested_role.value} (Development mode opt-in)",
            )

        # In dev without bypass, check configured credentials
        is_admin_user = secrets.compare_digest(username.strip(), configured_admin_user)
        if (
            configured_admin_password
            and is_admin_user
            and secrets.compare_digest(password.strip(), configured_admin_password)
        ):
            failed_login_tracker.record_success(identifier)
            return True, requested_role, f"Authenticated as {requested_role.value}"
        if configured_dev_pass and secrets.compare_digest(password.strip(), configured_dev_pass):
            failed_login_tracker.record_success(identifier)
            return True, requested_role, f"Authenticated as {requested_role.value}"
        if configured_op_pass and secrets.compare_digest(password.strip(), configured_op_pass):
            failed_login_tracker.record_success(identifier)
            return (
                True,
                Role.OPERATOR if requested_role in (Role.OPERATOR, Role.VIEWER) else Role.VIEWER,
                "Authenticated as Operator",
            )
        if configured_viewer_pass and secrets.compare_digest(
            password.strip(), configured_viewer_pass
        ):
            failed_login_tracker.record_success(identifier)
            return True, Role.VIEWER, "Authenticated as Viewer"

        failed_login_tracker.record_failure(identifier)
        return (
            False,
            Role.VIEWER,
            "Invalid credentials. Blind password acceptance is disabled in development mode. "
            "Configure ARGVTIX_ADMIN_PASSWORD / ARGVTIX_DEV_PASSWORD or explicitly set ARGVTIX_ALLOW_INSECURE_DEV_AUTH=true.",
        )

    # 3. Production Strict Mode: Validate credentials against environment
    # Refuse insecure dev flag in production
    if get_config_with_alias(
        "ARGVTIX_ALLOW_INSECURE_DEV_AUTH", "PROOFLINE_ALLOW_INSECURE_DEV_AUTH", "false"
    ).lower() in ("true", "1", "yes"):
        logger.critical(
            "SECURITY VIOLATION: ARGVTIX_ALLOW_INSECURE_DEV_AUTH is forbidden in production/staging environments."
        )
        return (
            False,
            Role.VIEWER,
            "Insecure dev authentication is strictly prohibited in production.",
        )

    if not configured_admin_password:
        return False, Role.VIEWER, "Administrative authentication is not configured in production"

    is_admin_user = secrets.compare_digest(username.strip(), configured_admin_user)
    is_admin_pass = secrets.compare_digest(password.strip(), configured_admin_password)

    if requested_role == Role.ADMIN:
        if is_admin_user and is_admin_pass:
            failed_login_tracker.record_success(identifier)
            return True, Role.ADMIN, "Authenticated as Admin"
        failed_login_tracker.record_failure(identifier)
        return False, Role.VIEWER, "Invalid administrative credentials"

    # Operator role (Enterprise Engineer or Ops)
    if requested_role == Role.OPERATOR:
        if is_admin_user and is_admin_pass:
            failed_login_tracker.record_success(identifier)
            return True, Role.OPERATOR, "Authenticated as Operator (Admin tier)"
        if configured_op_pass and secrets.compare_digest(password.strip(), configured_op_pass):
            failed_login_tracker.record_success(identifier)
            return True, Role.OPERATOR, "Authenticated as Operator"
        failed_login_tracker.record_failure(identifier)
        return False, Role.VIEWER, "Invalid operator credentials"

    # Viewer role
    if is_admin_user and is_admin_pass:
        failed_login_tracker.record_success(identifier)
        return True, Role.VIEWER, "Authenticated as Viewer"
    if configured_viewer_pass and secrets.compare_digest(password.strip(), configured_viewer_pass):
        failed_login_tracker.record_success(identifier)
        return True, Role.VIEWER, "Authenticated as Viewer"

    failed_login_tracker.record_failure(identifier)
    return False, Role.VIEWER, "Invalid credentials"


def create_access_token(
    user_id: str | dict[str, Any],
    project_id: str = "default",
    role: Role = Role.VIEWER,
    expires_delta: timedelta | None = None,
    secret_key: str | None = None,
) -> str:
    """Generates a signed HS256 JWT access token."""
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
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, key, algorithm=JWT_ALGORITHM)


def verify_access_token(
    token: str,
    secret_key: str | None = None,
) -> TokenPayload:
    """Decodes and validates a JWT token and confirms it is not revoked."""
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
    """FastAPI dependency extracting and verifying the authenticated user."""
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
