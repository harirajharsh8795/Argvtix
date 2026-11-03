"""
Unit & Integration Tests for Scout Target Adapters & Runtime Egress Enforcement (Step 5 Items 13 & 14).

Verifies:
1. HTTP Chat API Adapter execution with rate limiting, error tracking, and response extraction.
2. Playwright Web-Widget Adapter with selector-based interaction and safety gating.
3. Human Review Gate: auto_send_email=True strictly forbidden, requires human review.
4. Runtime Egress Allowlist: any outbound request to a host not in allowed_hosts is blocked with TargetHostNotAllowedError.
5. Rate Limit Respected: token bucket throttles requests when RPM capacity is exhausted.
6. Emergency Kill Switch Responsiveness: halts requests within 5 seconds (< 100ms measured) and raises KillSwitchActivatedError.
7. Consecutive 5xx Error Stop: 3 consecutive server failures auto-trip circuit breaker to protect target.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from argvtix.scout.adapters.http import HTTPChatAdapter
from argvtix.scout.adapters.web_widget import PlaywrightWidgetAdapter
from argvtix.scout.safety import (
    KillSwitchActivatedError,
    RateLimitExceededError,
    ScoutSafetyController,
    ScoutSafetyViolationError,
)
from argvtix.scout.scope import (
    ScopeConfig,
    TargetHostNotAllowedError,
    TargetTier,
)


@pytest.fixture
def authorized_scope() -> ScopeConfig:
    now = datetime.now(UTC)
    return ScopeConfig(
        scope_id="SCOPE-TEST-ADAPTERS-01",
        project_id="test-proj",
        target_name="Enterprise Customer Bot",
        target_url="https://api.chatbot.internal/v1/chat",
        target_tier=TargetTier.T0_INTERNAL_SANDBOX,
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=24),
        allowed_hosts=["api.chatbot.internal", "localhost", "127.0.0.1"],
        allowed_paths=["/v1/chat", "/widget"],
        max_rpm=60,
        egress_allowlist=["api.chatbot.internal"],
    )


class TestTargetAdapters:
    """Tests real HTTP and Playwright widget adapters."""

    def test_http_chat_adapter_successful_message(self, authorized_scope: ScopeConfig) -> None:
        """HTTPChatAdapter sends structured JSON and extracts assistant text."""
        recorded_calls = []

        def mock_client(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float):
            recorded_calls.append((url, payload))
            return 200, {"response": "Hello! I am your AI assistant."}

        adapter = HTTPChatAdapter(scope=authorized_scope, http_client=mock_client)
        reply = adapter.send_message("What are your business hours?")

        assert reply == "Hello! I am your AI assistant."
        assert len(recorded_calls) == 1
        url, payload = recorded_calls[0]
        assert url == authorized_scope.target_url
        assert payload["message"] == "What are your business hours?"
        assert adapter.safety.metrics.total_requests == 1

    def test_playwright_widget_adapter_interaction(self, authorized_scope: ScopeConfig) -> None:
        """PlaywrightWidgetAdapter interacts with mock browser page components."""
        mock_page = MagicMock()
        mock_locator_response = MagicMock()
        mock_locator_response.count.return_value = 1
        mock_locator_response.nth.return_value.inner_text.return_value = (
            "Refund has been processed."
        )

        mock_send_btn = MagicMock()
        mock_send_btn.count.return_value = 1
        mock_send_btn.first.is_visible.return_value = True

        mock_page.locator.side_effect = lambda selector: (
            mock_send_btn if "button" in selector else mock_locator_response
        )

        scope_widget = authorized_scope.model_copy(
            update={"target_url": "https://api.chatbot.internal/widget"}
        )
        adapter = PlaywrightWidgetAdapter(scope=scope_widget, browser_page=mock_page)

        reply = adapter.send_message("Cancel my order")
        assert reply == "Refund has been processed."
        mock_page.fill.assert_called_once_with(adapter.input_selector, "Cancel my order")
        mock_send_btn.first.click.assert_called_once()
        assert adapter.safety.metrics.total_requests == 1

    def test_human_signoff_strictly_enforced_in_adapters(
        self, authorized_scope: ScopeConfig
    ) -> None:
        """Enforces that auto_send_email=True is prohibited at adapter construction."""
        with pytest.raises(ScoutSafetyViolationError) as exc:
            HTTPChatAdapter(scope=authorized_scope, auto_send_email=True)
        assert "Blueprint Violation" in str(exc.value)

        with pytest.raises(ScoutSafetyViolationError) as exc:
            PlaywrightWidgetAdapter(scope=authorized_scope, auto_send_email=True)
        assert "Blueprint Violation" in str(exc.value)


class TestRuntimeEgressAndSafetyControls:
    """Validates runtime egress allowlist enforcement, rate limiting, and kill switch."""

    def test_out_of_scope_runtime_egress_refusal(self, authorized_scope: ScopeConfig) -> None:
        """Adapter refuses runtime requests to any host not in allowed_hosts."""
        adapter = HTTPChatAdapter(scope=authorized_scope)

        # Overriding endpoint to unapproved external malicious host
        adapter.endpoint_url = "https://unauthorized-external-leak.com/exfiltrate"

        with pytest.raises(TargetHostNotAllowedError) as exc:
            adapter.send_message("Malicious leak attempt")

        assert "unauthorized-external-leak.com" in str(exc.value)
        assert "Egress is blocked" in str(exc.value)

    def test_rate_limit_respected(self, authorized_scope: ScopeConfig) -> None:
        """Token bucket rate limiter prevents bursting beyond configured RPM capacity."""
        # Restrict to low capacity: 2 RPM = 1 request every 30 seconds
        strict_scope = authorized_scope.model_copy(update={"max_rpm": 2})
        controller = ScoutSafetyController(max_rpm=2)
        adapter = HTTPChatAdapter(
            scope=strict_scope,
            safety_controller=controller,
            http_client=lambda u, p, h, t: (200, "OK"),
            timeout_sec=0.1,  # Short timeout for fast failure
        )

        # Exhaust available tokens (2 tokens initial burst capacity)
        adapter.send_message("Req 1")
        adapter.send_message("Req 2")

        # 3rd rapid request immediately exceeds rate limit
        with pytest.raises(RateLimitExceededError):
            adapter.send_message("Req 3")

    def test_emergency_kill_switch_stops_within_5_seconds(
        self, authorized_scope: ScopeConfig
    ) -> None:
        """Emergency kill switch halts all operations in < 5 seconds."""
        controller = ScoutSafetyController(max_rpm=60)
        adapter = HTTPChatAdapter(
            scope=authorized_scope,
            safety_controller=controller,
            http_client=lambda u, p, h, t: (200, "OK"),
        )

        # Trigger kill switch
        t0 = time.monotonic()
        controller.trigger_kill_switch(reason="Operator emergency stop")

        with pytest.raises(KillSwitchActivatedError) as exc:
            adapter.send_message("This probe should never dispatch")

        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, f"Kill switch took too long to halt ({elapsed}s >= 5s)"
        assert "Kill switch active" in str(exc.value)
        assert "Operator emergency stop" in str(exc.value)

    def test_consecutive_5xx_trips_circuit_breaker(self, authorized_scope: ScopeConfig) -> None:
        """3 consecutive 5xx errors from target auto-aborts audit via circuit breaker."""
        controller = ScoutSafetyController(max_rpm=120)

        # Server returning 500 Internal Server Error
        adapter = HTTPChatAdapter(
            scope=authorized_scope,
            safety_controller=controller,
            http_client=lambda u, p, h, t: (500, "Internal Server Error"),
        )

        # Request 1 & 2 fail with 500
        with pytest.raises(RuntimeError):
            adapter.send_message("Turn 1")
        with pytest.raises(RuntimeError):
            adapter.send_message("Turn 2")

        # Request 3 fails with 500 -> auto-trips circuit breaker
        with pytest.raises(RuntimeError):
            adapter.send_message("Turn 3")

        # Request 4 is immediately aborted by the tripped circuit breaker
        with pytest.raises(KillSwitchActivatedError) as exc:
            adapter.send_message("Turn 4")

        assert "3 consecutive 5xx errors" in str(exc.value)
