"""
Watchdog Multi-Channel Alerting Pipeline.

Dispatches real-time security, policy, and anomaly alerts via:
1. In-memory queue (for dashboard polling and live visualization)
2. Slack Webhook (enterprise channel notifications)
3. Email notification (operations & incident response)
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage
from enum import Enum
from typing import Any

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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def fingerprint(self) -> str:
        """Computes deduplication fingerprint based on source, severity, title, and key entity."""
        entity = (
            self.metadata.get("entity_id")
            or self.metadata.get("order_id")
            or self.metadata.get("customer_id")
            or ""
        )
        return f"{self.source}:{self.severity.value}:{self.title}:{entity}"


class AlertDispatcher:
    """Manages routing, formatting, deduplicating, throttling, and dispatching alerts to configured sinks."""

    def __init__(
        self,
        max_in_memory: int = 100,
        slack_webhook_url: str | None = None,
        email_recipients: list[str] | None = None,
        http_post_fn: Callable[[str, dict[str, Any], float], bool] | None = None,
        smtp_sender_fn: Callable[[str, list[str], EmailMessage], bool] | None = None,
        dedup_window_seconds: float = 60.0,
        max_alerts_per_minute: int = 30,
    ) -> None:
        self._queue: deque[AlertPayload] = deque(maxlen=max_in_memory)
        self.slack_webhook_url = slack_webhook_url or os.getenv("ARGVTIX_SLACK_WEBHOOK_URL")
        self.email_recipients = email_recipients or [
            r.strip() for r in os.getenv("ARGVTIX_ALERT_EMAILS", "").split(",") if r.strip()
        ]

        self.smtp_host = os.getenv("ARGVTIX_SMTP_HOST", "localhost")
        self.smtp_port = int(os.getenv("ARGVTIX_SMTP_PORT", "587"))
        self.smtp_user = os.getenv("ARGVTIX_SMTP_USER", "")
        self.smtp_password = os.getenv("ARGVTIX_SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("ARGVTIX_SMTP_FROM", "alerts@argvtix.io")
        self.smtp_use_tls = os.getenv("ARGVTIX_SMTP_TLS", "false").lower() in ("true", "1", "yes")

        self._http_post_fn = http_post_fn
        self._smtp_sender_fn = smtp_sender_fn

        # Deduplication and Throttling
        self.dedup_window_seconds = dedup_window_seconds
        self.max_alerts_per_minute = max_alerts_per_minute
        self._dedup_history: dict[str, float] = {}
        self._dispatch_timestamps: deque[float] = deque()
        self.total_dispatched = 0
        self.total_suppressed = 0
        self.total_throttled = 0

    def is_duplicate(self, alert: AlertPayload, now: float | None = None) -> bool:
        """Checks if an alert is duplicate within the deduplication window."""
        import time

        current_time = now if now is not None else time.time()
        fp = alert.fingerprint()

        last_seen = self._dedup_history.get(fp)
        if last_seen is not None and (current_time - last_seen) < self.dedup_window_seconds:
            return True

        self._dedup_history[fp] = current_time
        # Clean old keys (> 10x dedup window)
        cutoff = current_time - (self.dedup_window_seconds * 2)
        self._dedup_history = {k: v for k, v in self._dedup_history.items() if v >= cutoff}
        return False

    def is_throttled(self, now: float | None = None) -> bool:
        """Checks if alert rate exceeds max_alerts_per_minute."""
        import time

        current_time = now if now is not None else time.time()
        minute_ago = current_time - 60.0

        # Purge timestamps older than 60 seconds
        while self._dispatch_timestamps and self._dispatch_timestamps[0] < minute_ago:
            self._dispatch_timestamps.popleft()

        if len(self._dispatch_timestamps) >= self.max_alerts_per_minute:
            return True

        self._dispatch_timestamps.append(current_time)
        return False

    def dispatch(
        self,
        alert: AlertPayload,
        channels: list[AlertChannel] | None = None,
        bypass_dedup: bool = False,
        bypass_throttle: bool = False,
    ) -> dict[str, bool]:
        """
        Dispatches an alert to specified channels with deduplication and throttling.
        Returns mapping of channel name -> success status (or suppressed/throttled flags).
        """
        if not bypass_dedup and self.is_duplicate(alert):
            self.total_suppressed += 1
            logger.info("[ALERT_DEDUP] Suppressed duplicate alert: %s", alert.fingerprint())
            return {"suppressed": True, "in_memory": False, "slack": False, "email": False}

        if not bypass_throttle and self.is_throttled():
            self.total_throttled += 1
            logger.warning(
                "[ALERT_THROTTLED] Rate limit reached (%s/min); alert dropped: %s",
                self.max_alerts_per_minute,
                alert.title,
            )
            return {"throttled": True, "in_memory": False, "slack": False, "email": False}

        self.total_dispatched += 1

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

        severity_color = (
            "#e01e5a"
            if alert.severity == AlertSeverity.CRITICAL
            else ("#ecb22e" if alert.severity == AlertSeverity.WARNING else "#2eb886")
        )

        payload = {
            "text": f"[{alert.severity.value.upper()}] {alert.title}\n{alert.message}",
            "attachments": [
                {
                    "color": severity_color,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Alert ID", "value": alert.alert_id, "short": True},
                        {"title": "Timestamp", "value": alert.timestamp.isoformat(), "short": True},
                    ],
                }
            ],
        }

        if self._http_post_fn is not None:
            return self._http_post_fn(self.slack_webhook_url, payload, 5.0)

        # Real HTTP dispatch
        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.slack_webhook_url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Argvtix-AlertDispatcher/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                status = resp.status if hasattr(resp, "status") else 200
                if 200 <= status < 300:
                    logger.info(
                        "[ALERT_SLACK_SENT] Dispatched alert %s to Slack webhook", alert.alert_id
                    )
                    return True
                logger.error("[ALERT_SLACK_ERROR] Non-2xx response from Slack: %s", status)
                return False
        except Exception as exc:
            logger.error(
                "[ALERT_SLACK_ERROR] Failed to dispatch Slack webhook %s: %s",
                self.slack_webhook_url,
                exc,
            )
            return False

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

        msg = EmailMessage()
        msg["Subject"] = f"[{alert.severity.value.upper()}] Argvtix Security Alert: {alert.title}"
        msg["From"] = self.smtp_from
        msg["To"] = ", ".join(self.email_recipients)

        body_lines = [
            f"Alert: {alert.title}",
            f"Severity: {alert.severity.value.upper()}",
            f"Source: {alert.source}",
            f"Alert ID: {alert.alert_id}",
            f"Timestamp: {alert.timestamp.isoformat()}",
            "",
            "Message:",
            alert.message,
            "",
            f"Metadata: {json.dumps(alert.metadata, indent=2)}",
        ]
        msg.set_content("\n".join(body_lines))

        if self._smtp_sender_fn is not None:
            return self._smtp_sender_fn(self.smtp_from, self.email_recipients, msg)

        # Real SMTP dispatch
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=5.0) as server:
                if self.smtp_use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info(
                "[ALERT_EMAIL_SENT] Dispatched alert %s to %s recipients",
                alert.alert_id,
                len(self.email_recipients),
            )
            return True
        except Exception as exc:
            logger.error(
                "[ALERT_EMAIL_ERROR] Failed to send alert email via %s:%s: %s",
                self.smtp_host,
                self.smtp_port,
                exc,
            )
            return False

    def get_recent_alerts(self, limit: int = 50) -> list[AlertPayload]:
        """Retrieves most recent alerts from in-memory ring buffer."""
        items = list(self._queue)
        return items[:limit]

    def clear(self) -> None:
        """Clears all buffered alerts and resets deduplication/throttling state."""
        self._queue.clear()
        self._dedup_history.clear()
        self._dispatch_timestamps.clear()
        self.total_dispatched = 0
        self.total_suppressed = 0
        self.total_throttled = 0


# Global singleton dispatcher instance
alert_dispatcher = AlertDispatcher()
