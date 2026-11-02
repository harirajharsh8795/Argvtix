"""Safety controls, rate limiting, kill switch, and circuit breakers for Argvtix Scout.

Safety Controls FIRST:
1. Token bucket rate limiter (default 1 req / 5s = 12 RPM).
2. Emergency kill switch (halts all outbound requests in < 5 seconds).
3. Auto-abort circuit breaker on 3 consecutive 5xx server errors.
4. Strict conversation and turn limits.
5. Human review gate (NO auto-outreach or automated emails).
"""

from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ScoutSafetyViolationError(Exception):
    """Raised when a safety control or boundary is breached."""

    pass


class KillSwitchActivatedError(ScoutSafetyViolationError):
    """Raised when the emergency kill switch has been triggered."""

    pass


class CircuitBreakerTrippedError(ScoutSafetyViolationError):
    """Raised when target service fails 3x consecutively (5xx responses)."""

    pass


class RateLimitExceededError(ScoutSafetyViolationError):
    """Raised when request rate exceeds allowed max_rpm."""

    pass


class SafetyMetrics(BaseModel):
    """Real-time telemetry for Scout safety controller."""

    total_requests: int = 0
    total_conversations: int = 0
    consecutive_5xx: int = 0
    kill_switch_active: bool = False
    kill_reason: str | None = None
    circuit_breaker_tripped: bool = False
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stopped_at: datetime | None = None


class RateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, max_rpm: int = 12):
        self.max_rpm = max(1, max_rpm)
        self.capacity = float(self.max_rpm)
        self.tokens = float(self.max_rpm)
        self.refill_rate = float(self.max_rpm) / 60.0  # tokens per second
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout_sec: float = 10.0) -> bool:
        """Blocks until a token is available or timeout expires."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True

            time.sleep(0.05)
        return False


class ScoutSafetyController:
    """Orchestrates kill switch, rate limits, circuit breaker, and human review gates."""

    def __init__(
        self,
        max_rpm: int = 12,
        max_turns_per_conversation: int = 8,
        max_conversations: int = 150,
        kill_file_path: str | Path | None = None,
        max_run_seconds: float = 900.0,  # 15 minutes max
    ):
        self.rate_limiter = RateLimiter(max_rpm=max_rpm)
        self.max_turns = max_turns_per_conversation
        self.max_conversations = max_conversations
        self.kill_file = Path(kill_file_path) if kill_file_path else Path(".scout_kill")
        self.max_run_seconds = max_run_seconds

        self._kill_event = threading.Event()
        self._lock = threading.RLock()
        self.metrics = SafetyMetrics()

    # --- Kill Switch Controls ---

    def trigger_kill_switch(self, reason: str = "Manual kill switch triggered") -> None:
        """Immediately halts all active and pending Scout operations (< 5s)."""
        with self._lock:
            self._kill_event.set()
            self.metrics.kill_switch_active = True
            self.metrics.kill_reason = reason
            self.metrics.stopped_at = datetime.now(UTC)

    def is_kill_switch_active(self) -> bool:
        """Checks programmatic event, file-based flag, and dead-man timer."""
        if self._kill_event.is_set():
            return True

        # Check file-based kill switch
        if self.kill_file.exists():
            self.trigger_kill_switch(f"Kill file '{self.kill_file}' detected on disk")
            return True

        # Check environment variable kill switch
        if os.environ.get("ARGVTIX_SCOUT_KILL", "").lower() in ("1", "true", "yes"):
            self.trigger_kill_switch("Environment variable ARGVTIX_SCOUT_KILL=1 detected")
            return True

        # Check dead-man timer
        runtime = (datetime.now(UTC) - self.metrics.started_at).total_seconds()
        if runtime > self.max_run_seconds:
            self.trigger_kill_switch(f"Max run duration ({self.max_run_seconds}s) exceeded")
            return True

        return False

    def check_safety_preflight(self, current_conversation_turns: int = 0) -> None:
        """Pre-flight check before making ANY outbound request.

        Raises KillSwitchActivatedError, CircuitBreakerTrippedError, ScoutSafetyViolationError.
        """
        if self.is_kill_switch_active():
            raise KillSwitchActivatedError(
                f"[SCOUT_HALTED] Kill switch active: {self.metrics.kill_reason or 'Emergency stop'}"
            )

        if self.metrics.circuit_breaker_tripped:
            raise CircuitBreakerTrippedError(
                "[SCOUT_HALTED] Circuit breaker tripped due to 3 consecutive 5xx errors."
            )

        if self.metrics.total_conversations >= self.max_conversations:
            raise ScoutSafetyViolationError(
                f"[SCOUT_HALTED] Max conversations limit reached ({self.max_conversations})."
            )

        if current_conversation_turns >= self.max_turns:
            raise ScoutSafetyViolationError(
                f"[SCOUT_HALTED] Max turns per conversation reached ({self.max_turns})."
            )

    def acquire_request_slot(self, timeout_sec: float = 10.0) -> None:
        """Applies rate limiting while checking kill switch responsiveness."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if self.is_kill_switch_active():
                raise KillSwitchActivatedError(
                    "[SCOUT_HALTED] Kill switch active during rate-limit wait."
                )

            if self.rate_limiter.acquire(timeout_sec=0.2):
                with self._lock:
                    self.metrics.total_requests += 1
                return

        raise RateLimitExceededError("Timed out waiting for rate limiter token slot.")

    # --- Circuit Breaker Controls ---

    def record_response(self, status_code: int) -> None:
        """Records HTTP status from target. Auto-trips circuit breaker on 3x 5xx."""
        with self._lock:
            if 500 <= status_code <= 599:
                self.metrics.consecutive_5xx += 1
                if self.metrics.consecutive_5xx >= 3:
                    self.metrics.circuit_breaker_tripped = True
                    self.trigger_kill_switch(
                        "Target server returned 3 consecutive 5xx errors; auto-aborted to protect target."
                    )
            else:
                self.metrics.consecutive_5xx = 0

    def start_conversation(self) -> None:
        """Increments conversation counter under lock."""
        with self._lock:
            self.metrics.total_conversations += 1

    # --- Human Review Gate ---

    @staticmethod
    def enforce_human_review_gate(allow_auto_email: bool = False) -> None:
        """Strictly disallows autonomous email sending or external contact."""
        if allow_auto_email:
            raise ScoutSafetyViolationError(
                "Blueprint Violation: Argvtix Scout NEVER auto-sends cold emails or contacts external leads. "
                "Audit reports must undergo human review and explicit operator sign-off."
            )
