"""
Tool Gateway Client Module.

Exposes protected tools over HTTP, MCP, or isolated boundary.
Ensures AI agents never directly import shop_tools or hold raw database sessions.
Enforces the Zero-Bypass principle: write actions cannot occur without passing Guard evaluation.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from argvtix.guard.engine import ActionGuard, GuardCheckRequest, GuardCheckResponse
from argvtix.guard.gateway import GatewayResult, ToolGateway
from argvtix.trace.schemas import GuardDecision

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ToolGatewayClient:
    """
    Client boundary used by AI agents to access enterprise tools.

    Guarantees:
    1. The AI Agent never imports shop_tools.
    2. The AI Agent never holds database sessions or direct write access.
    3. Every write action is evaluated by ActionGuard at the gateway boundary.
    """

    def __init__(
        self,
        base_url: str | None = None,
        mcp_server: Any | None = None,
        gateway: ToolGateway | None = None,
        db: Session | None = None,
        auth_token: str | None = None,
        stubbed_tools: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.mcp_server = mcp_server
        self._db = db
        self.auth_token = auth_token
        self.stubbed_tools: dict[str, Any] = stubbed_tools or {}

        # If an in-process gateway is provided or fallback to in-process boundary
        if gateway is not None:
            self._gateway = gateway
        elif self.base_url is None and self.mcp_server is None:
            self._gateway = ToolGateway()
        else:
            self._gateway = None

    def call_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        """
        Executes a tool call through the gateway boundary (HTTP, MCP, or Boundary Proxy).
        Enforces ActionGuard policy checks before any database write occurs.
        """
        # 0. Check for replay stubbing (used by Replay Levels L1-L3)
        if tool_name in self.stubbed_tools:
            stubbed = self.stubbed_tools[tool_name]
            if isinstance(stubbed, GatewayResult):
                return stubbed
            return GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.ALLOW,
                success=True,
                status="completed",
                data=stubbed if isinstance(stubbed, dict) else {"result": stubbed},
                idempotency_key=idempotency_key,
            )

        # 1. MCP Transport
        if self.mcp_server is not None:
            return self._call_via_mcp(tool_name, params, idempotency_key)

        # 2. HTTP REST Transport
        if self.base_url is not None:
            return self._call_via_http(tool_name, params, idempotency_key)

        # 3. In-process Gateway Boundary
        return self._call_via_boundary(tool_name, params, idempotency_key)

    def check_guard(self, request: GuardCheckRequest) -> GuardCheckResponse:
        """Evaluates whether an intended action satisfies safety guard policies."""
        if self.base_url is not None:
            return self._check_guard_via_http(request)

        # Boundary evaluation
        guard = self._gateway.guard if self._gateway else ActionGuard()
        if self._db is not None:
            return guard.evaluate(request, self._db)

        from argvtix.db.session import SessionLocal

        session = SessionLocal()
        try:
            return guard.evaluate(request, session)
        finally:
            session.close()

    def _call_via_boundary(
        self,
        tool_name: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        gateway = self._gateway or ToolGateway()
        if self._db is not None:
            return gateway.call(
                tool_name=tool_name,
                params=params,
                db=self._db,
                idempotency_key=idempotency_key,
            )

        from argvtix.db.session import SessionLocal

        session = SessionLocal()
        try:
            return gateway.call(
                tool_name=tool_name,
                params=params,
                db=session,
                idempotency_key=idempotency_key,
            )
        finally:
            session.close()

    def _call_via_http(
        self,
        tool_name: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        import urllib.error
        import urllib.request

        url = f"{self.base_url}/api/v1/guard/gateway/call"
        payload = {
            "tool_name": tool_name,
            "params": params,
            "idempotency_key": idempotency_key,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                result_json = json.loads(resp.read().decode("utf-8"))
                return GatewayResult.model_validate(result_json)
        except urllib.error.HTTPError as exc:
            try:
                err_body = json.loads(exc.read().decode("utf-8"))
                err_detail = err_body.get("detail", str(exc))
            except Exception:
                err_detail = str(exc)
            return GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.BLOCK,
                success=False,
                status="error",
                error=f"HTTP {exc.code}: {err_detail}",
            )
        except Exception as exc:
            return GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.BLOCK,
                success=False,
                status="error",
                error=f"Connection error to Tool Gateway HTTP endpoint: {exc}",
            )

    def _check_guard_via_http(self, request: GuardCheckRequest) -> GuardCheckResponse:
        import urllib.request

        url = f"{self.base_url}/api/v1/guard/check"
        data_bytes = request.model_dump_json().encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                result_json = json.loads(resp.read().decode("utf-8"))
                return GuardCheckResponse.model_validate(result_json)
        except Exception as exc:
            logger.error("HTTP guard check failed: %s", exc)
            return GuardCheckResponse(
                decision=GuardDecision.BLOCK,
                reason=f"Gateway policy check failed: {exc}",
            )

    def _call_via_mcp(
        self,
        tool_name: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        mcp_req = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params,
                "idempotency_key": idempotency_key,
            },
        }
        if hasattr(self.mcp_server, "handle"):
            mcp_resp_dict = self.mcp_server.handle(mcp_req)
        elif hasattr(self.mcp_server, "handle_request"):
            mcp_resp_dict = self.mcp_server.handle_request(mcp_req).model_dump()
        else:
            raise ValueError("Unknown MCP server interface")

        error = mcp_resp_dict.get("error")
        if error:
            error_code = error.get("code")
            error_msg = error.get("message", "MCP Error")
            decision = GuardDecision.ASK_HUMAN if error_code == -32003 else GuardDecision.BLOCK
            return GatewayResult(
                tool_name=tool_name,
                decision=decision,
                success=False,
                status="blocked" if decision == GuardDecision.BLOCK else "pending_approval",
                error=error_msg,
            )

        res_data = mcp_resp_dict.get("result", {})
        parsed_data = {}
        if "content" in res_data and isinstance(res_data["content"], list):
            for c in res_data["content"]:
                if c.get("type") == "text" and "text" in c:
                    try:
                        parsed_data = json.loads(c["text"])
                    except Exception:
                        parsed_data = {"raw": c["text"]}
        elif "data" in res_data:
            parsed_data = res_data["data"]
        else:
            parsed_data = res_data

        if res_data.get("pendingApproval"):
            return GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.ASK_HUMAN,
                success=False,
                status="pending_approval",
                approval_id=res_data.get("approvalId"),
                data=parsed_data,
                idempotency_key=idempotency_key,
            )

        return GatewayResult(
            tool_name=tool_name,
            decision=GuardDecision.ALLOW,
            success=True,
            status="completed",
            data=parsed_data,
            idempotency_key=idempotency_key,
        )
