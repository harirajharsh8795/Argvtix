"""Argvtix Python Client for API interaction."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger("argvtix_sdk")


class ArgvtixClientError(Exception):
    """Base exception for Argvtix API errors."""

    pass


class ArgvtixClient:
    """Synchronous client for communicating with Argvtix Gateway API."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str | None = None,
        project_id: str = "default",
        timeout: float = 10.0,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.project_id = project_id
        self.timeout = timeout
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_health(self) -> dict[str, Any]:
        """Checks platform and database health."""
        try:
            resp = self._session.get(f"{self.api_url}/health", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise ArgvtixClientError(f"Health check failed: {e}") from e

    def log_trace(self, trace_data: dict[str, Any]) -> dict[str, Any]:
        """Submits an execution trace to the Argvtix platform."""
        trace_data.setdefault("project_id", self.project_id)
        try:
            resp = self._session.post(
                f"{self.api_url}/api/v1/traces",
                json=trace_data,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("Failed to dispatch trace to Argvtix: %s", e)
            return {"status": "buffered_locally", "error": str(e)}

    def check_guard(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        order_id: str | None = None,
        amount: float | None = None,
        agent_id: str = "sdk-agent",
    ) -> dict[str, Any]:
        """Evaluates pre-action safety guard policies without tool execution."""
        payload = {
            "tool_name": tool_name,
            "parameters": parameters,
            "order_id": order_id,
            "amount": amount,
            "agent_id": agent_id,
            "project_id": self.project_id,
        }
        try:
            resp = self._session.post(
                f"{self.api_url}/api/v1/guard/check",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise ArgvtixClientError(f"Guard check failed: {e}") from e

    def call_gateway(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        order_id: str | None = None,
        amount: float | None = None,
        agent_id: str = "sdk-agent",
    ) -> dict[str, Any]:
        """Calls Tool Gateway MCP proxy for zero-bypass policy evaluation and execution."""
        payload = {
            "tool_name": tool_name,
            "parameters": parameters,
            "order_id": order_id,
            "amount": amount,
            "agent_id": agent_id,
            "project_id": self.project_id,
        }
        try:
            resp = self._session.post(
                f"{self.api_url}/api/v1/guard/gateway/call",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise ArgvtixClientError(f"Gateway execution failed: {e}") from e

    def get_spend_summary(self) -> dict[str, Any]:
        """Retrieves LLM token spend metrics and cap enforcement status."""
        try:
            resp = self._session.get(
                f"{self.api_url}/api/v1/spend/summary",
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise ArgvtixClientError(f"Failed to fetch spend summary: {e}") from e
