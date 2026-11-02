"""Tests for Scout safety controller, kill switch, rate limiting, and circuit breaker."""

import time
from pathlib import Path
import pytest

from argvtix.scout.safety import (
    KillSwitchActivatedError,
    RateLimiter,
    ScoutSafetyController,
    ScoutSafetyViolationError,
)


class TestScoutSafety:
    def test_rate_limiter_acquires_tokens(self):
        limiter = RateLimiter(max_rpm=60)
        assert limiter.acquire(timeout_sec=1.0) is True

    def test_programmatic_kill_switch_halts_immediately(self):
        controller = ScoutSafetyController(max_rpm=60)
        assert controller.is_kill_switch_active() is False

        start = time.monotonic()
        controller.trigger_kill_switch("Emergency test abort")
        elapsed = time.monotonic() - start

        assert elapsed < 1.0  # Well under 5 second requirement
        assert controller.is_kill_switch_active() is True

        with pytest.raises(KillSwitchActivatedError, match="Kill switch active"):
            controller.check_safety_preflight()

    def test_file_based_kill_switch(self, tmp_path: Path):
        kill_file = tmp_path / ".scout_kill"
        controller = ScoutSafetyController(max_rpm=60, kill_file_path=kill_file)

        assert controller.is_kill_switch_active() is False

        # Create kill file
        kill_file.write_text("ABORT", encoding="utf-8")
        assert controller.is_kill_switch_active() is True

        with pytest.raises(KillSwitchActivatedError):
            controller.check_safety_preflight()

    def test_env_var_kill_switch(self, monkeypatch: pytest.MonkeyPatch):
        controller = ScoutSafetyController(max_rpm=60)
        assert controller.is_kill_switch_active() is False

        monkeypatch.setenv("ARGVTIX_SCOUT_KILL", "1")
        assert controller.is_kill_switch_active() is True

    def test_circuit_breaker_trips_on_three_consecutive_5xx(self):
        controller = ScoutSafetyController(max_rpm=60)

        # Two 500s do not trip
        controller.record_response(500)
        controller.record_response(502)
        assert controller.metrics.circuit_breaker_tripped is False

        # Intervening 200 resets count
        controller.record_response(200)
        assert controller.metrics.consecutive_5xx == 0

        # Three consecutive 5xx trips breaker
        controller.record_response(500)
        controller.record_response(503)
        controller.record_response(504)

        assert controller.metrics.circuit_breaker_tripped is True
        assert controller.is_kill_switch_active() is True

        with pytest.raises(KillSwitchActivatedError):
            controller.check_safety_preflight()

    def test_max_turns_and_conversations_limits(self):
        controller = ScoutSafetyController(max_rpm=60, max_turns_per_conversation=3, max_conversations=2)

        # 3 turns ok, turn 4 blocked
        controller.check_safety_preflight(current_conversation_turns=2)
        with pytest.raises(ScoutSafetyViolationError, match="Max turns"):
            controller.check_safety_preflight(current_conversation_turns=3)

        # Conversation counter limit
        controller.start_conversation()
        controller.start_conversation()
        with pytest.raises(ScoutSafetyViolationError, match="Max conversations"):
            controller.check_safety_preflight(current_conversation_turns=0)

    def test_human_review_gate_forbids_auto_email(self):
        # Must raise violation if auto_send_email is True
        with pytest.raises(ScoutSafetyViolationError, match="NEVER auto-sends cold emails"):
            ScoutSafetyController.enforce_human_review_gate(allow_auto_email=True)

        # False passes
        ScoutSafetyController.enforce_human_review_gate(allow_auto_email=False)
