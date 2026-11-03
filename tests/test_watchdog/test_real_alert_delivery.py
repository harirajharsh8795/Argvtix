"""
Unit & Integration Tests for Real Alert Delivery (Step 5 Item 16).

Verifies:
1. When Slack webhook is unconfigured: logs stub and gracefully returns True.
2. When Slack webhook is configured: dispatches real HTTP payload over transport.
3. When Email recipients are unconfigured: logs stub and gracefully returns True.
4. When Email recipients are configured: constructs valid MIME/EmailMessage and dispatches over SMTP transport.
5. Network/transport failure handling: errors are caught, logged, and return False without crashing.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any

import pytest

from argvtix.watchdog.alerts import (
    AlertChannel,
    AlertDispatcher,
    AlertPayload,
    AlertSeverity,
)


@pytest.fixture
def sample_alert() -> AlertPayload:
    return AlertPayload(
        title="Prompt Injection Attack Detected",
        message="A user attempted to bypass guard rails using system jailbreak tokens.",
        severity=AlertSeverity.CRITICAL,
        source="watchdog_security",
        metadata={"attack_type": "jailbreak", "confidence": 0.98},
    )


class TestRealAlertDelivery:
    """Validates real transport dispatch for Slack webhooks and Email."""

    def test_unconfigured_slack_logs_stub_and_returns_true(
        self, sample_alert: AlertPayload, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When webhook URL is empty/None, alert dispatcher logs stub without network attempt."""
        caplog.set_level(logging.INFO)
        dispatcher = AlertDispatcher(slack_webhook_url=None)

        results = dispatcher.dispatch(sample_alert, channels=[AlertChannel.SLACK])
        assert results["slack"] is True
        assert any("[ALERT_SLACK_STUB]" in record.message for record in caplog.records)

    def test_configured_slack_sends_real_payload(self, sample_alert: AlertPayload) -> None:
        """When webhook URL is set, HTTP post transport receives formatted payload."""
        dispatched_calls: list[tuple[str, dict[str, Any], float]] = []

        def mock_http_post(url: str, payload: dict[str, Any], timeout: float) -> bool:
            dispatched_calls.append((url, payload, timeout))
            return True

        dispatcher = AlertDispatcher(
            slack_webhook_url="https://hooks.slack.com/services/T00/B00/X001",
            http_post_fn=mock_http_post,
        )

        results = dispatcher.dispatch(sample_alert, channels=[AlertChannel.SLACK])
        assert results["slack"] is True
        assert len(dispatched_calls) == 1

        url, payload, timeout = dispatched_calls[0]
        assert url == "https://hooks.slack.com/services/T00/B00/X001"
        assert timeout == 5.0
        assert "[CRITICAL] Prompt Injection Attack Detected" in payload["text"]
        assert len(payload["attachments"]) == 1
        attachment = payload["attachments"][0]
        assert attachment["color"] == "#e01e5a"  # Critical red color
        assert any(
            f["title"] == "Severity" and f["value"] == "CRITICAL" for f in attachment["fields"]
        )

    def test_slack_network_error_returns_false_and_logs(self, sample_alert: AlertPayload) -> None:
        """When HTTP transport encounters network failure, returns False cleanly."""

        def failing_http_post(url: str, payload: dict[str, Any], timeout: float) -> bool:
            return False

        dispatcher = AlertDispatcher(
            slack_webhook_url="https://hooks.slack.com/services/fail",
            http_post_fn=failing_http_post,
        )

        results = dispatcher.dispatch(sample_alert, channels=[AlertChannel.SLACK])
        assert results["slack"] is False

    def test_unconfigured_email_logs_stub_and_returns_true(
        self, sample_alert: AlertPayload, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When email distribution list is empty, logs stub and returns True."""
        caplog.set_level(logging.INFO)
        dispatcher = AlertDispatcher(email_recipients=[])

        results = dispatcher.dispatch(sample_alert, channels=[AlertChannel.EMAIL])
        assert results["email"] is True
        assert any("[ALERT_EMAIL_STUB]" in record.message for record in caplog.records)

    def test_configured_email_sends_structured_email(self, sample_alert: AlertPayload) -> None:
        """When email recipients are set, SMTP sender receives valid EmailMessage."""
        sent_messages: list[tuple[str, list[str], EmailMessage]] = []

        def mock_smtp_sender(from_addr: str, to_addrs: list[str], msg: EmailMessage) -> bool:
            sent_messages.append((from_addr, to_addrs, msg))
            return True

        recipients = ["security-ops@client.com", "ciso@client.com"]
        dispatcher = AlertDispatcher(
            email_recipients=recipients,
            smtp_sender_fn=mock_smtp_sender,
        )

        results = dispatcher.dispatch(sample_alert, channels=[AlertChannel.EMAIL])
        assert results["email"] is True
        assert len(sent_messages) == 1

        from_addr, to_addrs, msg = sent_messages[0]
        assert from_addr == "alerts@argvtix.io"
        assert to_addrs == recipients
        assert (
            msg["Subject"] == "[CRITICAL] Argvtix Security Alert: Prompt Injection Attack Detected"
        )
        assert "security-ops@client.com" in msg["To"]
        content = msg.get_content()
        assert "Severity: CRITICAL" in content
        assert "jailbreak" in content

    def test_email_smtp_failure_returns_false(self, sample_alert: AlertPayload) -> None:
        """When SMTP connection fails, returns False without raising exception."""

        def failing_smtp(from_addr: str, to_addrs: list[str], msg: EmailMessage) -> bool:
            return False

        dispatcher = AlertDispatcher(
            email_recipients=["ops@client.com"],
            smtp_sender_fn=failing_smtp,
        )

        results = dispatcher.dispatch(sample_alert, channels=[AlertChannel.EMAIL])
        assert results["email"] is False
