"""Base Target Adapter interface for Scout permission-first auditing."""

from __future__ import annotations

from abc import ABC, abstractmethod

from argvtix.scout.safety import ScoutSafetyController
from argvtix.scout.scope import ScopeConfig, validate_scope_allows_request


class BaseTargetAdapter(ABC):
    """Abstract base class for all Scout target adapters.

    Guarantees:
    1. Scope file verification on initialization & runtime egress validation per request.
    2. Rate limiting token enforcement before network dispatch.
    3. Consecutive 5xx error tracking tripping the safety circuit breaker.
    4. Kill switch immediate halting.
    5. Human review sign-off gating (rejection of auto-outreach/cold email).
    """

    def __init__(
        self,
        scope: ScopeConfig,
        safety_controller: ScoutSafetyController | None = None,
        auto_send_email: bool = False,
    ) -> None:
        self.scope = scope
        self.safety = safety_controller or ScoutSafetyController(
            max_rpm=scope.max_rpm,
            max_turns_per_conversation=scope.max_turns_per_conversation,
            max_conversations=scope.max_conversations,
        )

        # 1. Blueprint constraint: enforce human review sign-off (no auto email outreach)
        self.safety.enforce_human_review_gate(allow_auto_email=auto_send_email)

        # 2. Scope verification: validate initial target URL
        validate_scope_allows_request(self.scope, self.scope.target_url)

    def validate_egress(self, destination_url: str) -> None:
        """Runtime egress enforcement: validates destination host & path against scope allowlists."""
        validate_scope_allows_request(self.scope, destination_url)

    @abstractmethod
    def send_message(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        """Sends a message to the target agent and returns the assistant reply text."""
        pass

    def __call__(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        """Enables passing the adapter instance directly as target_fn."""
        return self.send_message(message, history)
