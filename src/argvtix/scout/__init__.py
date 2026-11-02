"""Argvtix Scout: Permission-First Legal AI Chatbot Audit Platform."""

from argvtix.scout.container import generate_scout_sandbox_compose, validate_egress_destination
from argvtix.scout.oracles.engine import CompositeOracleVerdict, OracleEngine
from argvtix.scout.probes.base import (
    ProbeCategory,
    ProbeExecutionResult,
    ProbeSeverity,
    ProbeTurn,
    ScoutProbe,
)
from argvtix.scout.report import (
    AuditGrade,
    AuditStatus,
    ScoutAuditReport,
    calculate_grade,
)
from argvtix.scout.runner import ScoutRunner
from argvtix.scout.safety import (
    CircuitBreakerTrippedError,
    KillSwitchActivatedError,
    RateLimitExceededError,
    ScoutSafetyController,
    ScoutSafetyViolationError,
)
from argvtix.scout.scope import (
    MissingAuthorizationError,
    ScopeConfig,
    ScopeExpiredError,
    ScoutPermissionError,
    TargetHostNotAllowedError,
    TargetPathNotAllowedError,
    TargetTier,
    compute_scope_signature,
    load_scope_from_yaml,
    validate_scope_allows_request,
    verify_scope_signature,
)

__all__ = [
    "TargetTier",
    "ScopeConfig",
    "ScoutPermissionError",
    "ScopeExpiredError",
    "TargetHostNotAllowedError",
    "TargetPathNotAllowedError",
    "MissingAuthorizationError",
    "compute_scope_signature",
    "verify_scope_signature",
    "load_scope_from_yaml",
    "validate_scope_allows_request",
    "ScoutSafetyController",
    "ScoutSafetyViolationError",
    "KillSwitchActivatedError",
    "CircuitBreakerTrippedError",
    "RateLimitExceededError",
    "generate_scout_sandbox_compose",
    "validate_egress_destination",
    "ProbeCategory",
    "ProbeSeverity",
    "ProbeTurn",
    "ScoutProbe",
    "ProbeExecutionResult",
    "OracleEngine",
    "CompositeOracleVerdict",
    "AuditGrade",
    "AuditStatus",
    "ScoutAuditReport",
    "calculate_grade",
    "ScoutRunner",
]
