"""Scope verification and permission model for Argvtix Scout.

Scout strictly operates under a permission-first legal model. Probing is only
permitted against targets defined in a valid, cryptographically signed scope.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field, field_validator


class TargetTier(str, Enum):
    """Target environment risk tier."""

    T0_INTERNAL_SANDBOX = "T0_INTERNAL_SANDBOX"  # Localhost, test containers
    T1_CLIENT_STAGING = "T1_CLIENT_STAGING"  # Client test/staging environment
    T2_CLIENT_PRODUCTION = "T2_CLIENT_PRODUCTION"  # Client production with written consent
    T3_AUTHORIZED_API = "T3_AUTHORIZED_API"  # Third-party API with signed authorization


class ScoutPermissionError(Exception):
    """Base error for all Scout permission and scope violations."""

    pass


class ScopeExpiredError(ScoutPermissionError):
    """Scope validity time window is in the past or future."""

    pass


class TargetHostNotAllowedError(ScoutPermissionError):
    """Target host is not included in the allowed_hosts or egress_allowlist."""

    pass


class TargetPathNotAllowedError(ScoutPermissionError):
    """Target path is not allowed in scope."""

    pass


class MissingAuthorizationError(ScoutPermissionError):
    """Missing required signoff or authorization ID for non-sandbox targets."""

    pass


class InvalidSignatureError(ScoutPermissionError):
    """Scope cryptographic signature failed verification."""

    pass


class ScopeConfig(BaseModel):
    """Cryptographically verifiable scope definition for an audit run."""

    scope_id: str = Field(description="Unique scope identifier")
    project_id: str = Field(default="default", description="Associated Argvtix project ID")
    target_name: str = Field(description="Human-readable name of target agent/chatbot")
    target_url: str = Field(description="Target endpoint URL (e.g., http://localhost:8000/chat)")
    target_tier: TargetTier = Field(default=TargetTier.T0_INTERNAL_SANDBOX)
    written_authorization_id: str = Field(
        default="",
        description="Formal contract or legal authorization reference (e.g. AUTH-2026-CLIENT-09)",
    )
    signoff_contact_email: str = Field(
        default="", description="Authorized representative contact email (e.g. ciso@client.com)"
    )
    valid_from: datetime = Field(description="Audit window start UTC")
    valid_until: datetime = Field(description="Audit window end UTC")
    allowed_hosts: list[str] = Field(
        default_factory=list, description="List of hostnames or IPs Scout is allowed to connect to"
    )
    allowed_paths: list[str] = Field(
        default_factory=lambda: ["/"],
        description="List of URL path prefixes Scout is permitted to probe",
    )
    max_rpm: int = Field(
        default=12, ge=1, le=120, description="Max requests per minute (default 12 = 1 per 5s)"
    )
    max_turns_per_conversation: int = Field(default=8, ge=1, le=20)
    max_conversations: int = Field(default=150, ge=1, le=500)
    egress_allowlist: list[str] = Field(
        default_factory=list,
        description="Firewall egress allowlist for container network isolation",
    )
    signature: str | None = Field(
        default=None, description="HMAC-SHA256 signature over canonical scope fields"
    )

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def normalize_allowed_hosts(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [v.strip().lower()]
        if isinstance(v, list):
            return [str(h).strip().lower() for h in v]
        return []

    def canonical_dict(self) -> dict[str, Any]:
        """Returns deterministic dictionary representation for cryptographic signing."""
        return {
            "scope_id": self.scope_id,
            "project_id": self.project_id,
            "target_name": self.target_name,
            "target_url": self.target_url,
            "target_tier": self.target_tier.value,
            "written_authorization_id": self.written_authorization_id,
            "signoff_contact_email": self.signoff_contact_email,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "allowed_hosts": sorted(self.allowed_hosts),
            "allowed_paths": sorted(self.allowed_paths),
            "max_rpm": self.max_rpm,
            "max_turns_per_conversation": self.max_turns_per_conversation,
            "max_conversations": self.max_conversations,
        }


def compute_scope_signature(scope: ScopeConfig | dict[str, Any], secret_key: str) -> str:
    """Computes HMAC-SHA256 signature for canonical scope fields."""
    if isinstance(scope, ScopeConfig):
        canonical = scope.canonical_dict()
    else:
        # Filter to canonical keys
        canonical = {
            k: scope.get(k)
            for k in [
                "scope_id",
                "project_id",
                "target_name",
                "target_url",
                "target_tier",
                "written_authorization_id",
                "signoff_contact_email",
                "valid_from",
                "valid_until",
                "allowed_hosts",
                "allowed_paths",
                "max_rpm",
                "max_turns_per_conversation",
                "max_conversations",
            ]
        }
    payload_str = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        secret_key.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_scope_signature(scope: ScopeConfig, secret_key: str) -> bool:
    """Verifies that scope.signature matches computed HMAC."""
    if not scope.signature:
        return False
    expected = compute_scope_signature(scope, secret_key)
    return hmac.compare_digest(scope.signature, expected)


def load_scope_from_yaml(
    source: str | Path | dict[str, Any],
    secret_key: str | None = None,
    enforce_signature: bool = False,
) -> ScopeConfig:
    """Loads and validates a scope from YAML string, filepath, or dictionary."""
    if isinstance(source, (str, Path)):
        p = Path(source)
        if p.exists() and p.is_file():
            content = p.read_text(encoding="utf-8")
            raw = yaml.safe_load(content)
        else:
            raw = yaml.safe_load(str(source))
    elif isinstance(source, dict):
        raw = source
    else:
        raise ValueError(f"Unsupported source type: {type(source)}")

    if not isinstance(raw, dict):
        raise ScoutPermissionError("Scope configuration must be a dictionary or YAML document.")

    scope = ScopeConfig.model_validate(raw)

    if enforce_signature:
        if not secret_key:
            raise ScoutPermissionError(
                "Secret key required to enforce scope signature verification."
            )
        if not verify_scope_signature(scope, secret_key):
            raise InvalidSignatureError(
                "Scope signature verification failed: scope may have been tampered with."
            )

    return scope


def validate_scope_allows_request(
    scope: ScopeConfig,
    target_url: str,
    current_time: datetime | None = None,
) -> None:
    """Ensures target_url is strictly authorized under the scope.

    Raises:
        ScopeExpiredError
        MissingAuthorizationError
        TargetHostNotAllowedError
        TargetPathNotAllowedError
    """
    now = current_time or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    vf = scope.valid_from if scope.valid_from.tzinfo else scope.valid_from.replace(tzinfo=UTC)
    vu = scope.valid_until if scope.valid_until.tzinfo else scope.valid_until.replace(tzinfo=UTC)

    if now < vf or now > vu:
        raise ScopeExpiredError(
            f"Scope '{scope.scope_id}' is not active. Valid window: {vf.isoformat()} to {vu.isoformat()}, now: {now.isoformat()}"
        )

    # For non-sandbox tiers (T1, T2, T3), written authorization is mandatory
    if scope.target_tier != TargetTier.T0_INTERNAL_SANDBOX:
        if not scope.written_authorization_id.strip():
            raise MissingAuthorizationError(
                f"Scope tier {scope.target_tier.value} requires a non-empty written_authorization_id."
            )
        if not scope.signoff_contact_email.strip() or "@" not in scope.signoff_contact_email:
            raise MissingAuthorizationError(
                f"Scope tier {scope.target_tier.value} requires a valid signoff_contact_email."
            )

    parsed = urlparse(target_url)
    host = (parsed.hostname or "").lower()
    port = parsed.port
    path = parsed.path or "/"

    host_with_port = f"{host}:{port}" if port else host

    # Allowed hosts check
    allowed = {h.lower() for h in scope.allowed_hosts}
    # Also add egress allowlist if specified
    if scope.egress_allowlist:
        allowed.update({h.lower() for h in scope.egress_allowlist})

    host_matched = (host in allowed) or (host_with_port in allowed)
    if not host_matched:
        raise TargetHostNotAllowedError(
            f"Target host '{host}' is not in allowed_hosts ({sorted(allowed)}). Egress is blocked."
        )

    # Allowed paths check
    path_matched = False
    for p in scope.allowed_paths:
        if path.startswith(p):
            path_matched = True
            break
    if not path_matched:
        raise TargetPathNotAllowedError(
            f"Target path '{path}' is not within permitted allowed_paths ({scope.allowed_paths})."
        )
