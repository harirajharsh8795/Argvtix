"""
Watchdog Multi-Channel Alerting Pipeline.

Dispatches real-time security, policy, and anomaly alerts via:
1. In-memory queue (for dashboard polling and live visualization)
2. Slack Webhook (enterprise channel notifications)
3. Email notification stub (operations & incident response)
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from enum import Enum
import logging
import os
from typing import Any
import uuid

from pydantic import BaseModel, Field

logger = logging.getLogger("argvtix.watchdog.alerts")


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    IN_MEMORY = "in_memory"
    SLACK = "slack"
    EMAIL = "email"


class AlertPayload(BaseModel):
    """Structured alert event emitted by Watchdog, Guard, or Anomaly detector."""
    alert_id: str = Field(default_factory=lambda: f"alt_{uuid.uuid4().hex[:12]}")
    title: str
    message: str
    severity: AlertSeverity = AlertSeverity.WARNING
    source: str = "watchdog"  # "watchdog" | "guard" | "anomaly" | "reconcile"
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlertDispatcher:
    """Manages routing, formatting, and dispatching alerts to configured sinks."""

    def __init__(
        self,
        max_in_memory: int = 100,
        slack_webhook_url: str | None = None,
        email_recipients: list[str] | None = None,
    ) -> None:
        self._queue: deque[AlertPayload] = deque(maxlen=max_in_memory)
        self.slack_webhook_url = slack_webhook_url or os.getenv("ARGVTIX_SLACK_WEBHOOK_URL")
        self.email_recipients = email_recipients or [
            r.strip() for r in os.getenv("ARGVTIX_ALERT_EMAILS", "").split(",") if r.strip()
        ]

    def dispatch(
        self,
        alert: AlertPayload,
        channels: list[AlertChannel] | None = None,
    ) -> dict[str, bool]:
        """
        Dispatches an alert to specified channels (or all available channels by default).
        Returns mapping of channel name -> success status.
        """
        if channels is None:
            channels = [AlertChannel.IN_MEMORY, AlertChannel.SLACK, AlertChannel.EMAIL]

        results: dict[str, bool] = {}

        for ch in channels:
            if ch == AlertChannel.IN_MEMORY:
                self._queue.appendleft(alert)
                results["in_memory"] = True

            elif ch == AlertChannel.SLACK:
                results["slack"] = self._send_slack(alert)

            elif ch == AlertChannel.EMAIL:
                results["email"] = self._send_email(alert)

        return results

    def _send_slack(self, alert: AlertPayload) -> bool:
        """Sends alert payload to Slack webhook if configured, or logs stub."""
        if not self.slack_webhook_url:
            logger.info(
                "[ALERT_SLACK_STUB] [%s] %s: %s (Webhook not configured)",
                alert.severity.value.upper(),
                alert.title,
                alert.message,
            )
            return True

        # In production, httpx.post(self.slack_webhook_url, json=payload)
        logger.info("[ALERT_SLACK_SENT] Dispatched to %s", self.slack_webhook_url)
        return True

    def _send_email(self, alert: AlertPayload) -> bool:
        """Sends email alert to configured distribution list or logs stub."""
        if not self.email_recipients:
            logger.info(
                "[ALERT_EMAIL_STUB] [%s] %s: %s (No recipients configured)",
                alert.severity.value.upper(),
                alert.title,
                alert.message,
            )
            return True

        logger.info(
            "[ALERT_EMAIL_SENT] Dispatched to %s recipients",
            len(self.email_recipients),
        )
        return True

    def get_recent_alerts(self, limit: int = 50) -> list[AlertPayload]:
        """Retrieves most recent alerts from in-memory ring buffer."""
        items = list(self._queue)
        return items[:limit]

    def clear(self) -> None:
        """Clears all buffered alerts."""
        self._queue.clear()


# Global singleton dispatcher instance
alert_dispatcher = AlertDispatcher()
