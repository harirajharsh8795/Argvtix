"""Tool Gateway Client for agent frameworks."""

from __future__ import annotations

from typing import Any, Callable, Optional
from pydantic import BaseModel, Field
from argvtix_sdk.client import ArgvtixClient


class GatewayExecutionResult(BaseModel):
    """Result of calling a tool through the Argvtix Tool Gateway."""
    tool_name: str
    decision: str = Field(description="'ALLOW', 'BLOCK', or 'ASK_HUMAN'")
    allowed: bool
    result: Optional[dict[str, Any]] = None
    violation_reason: Optional[str] = None
    approval_id: Optional[str] = None
    requires_approval: bool = False


class ToolGatewayClient:
    """Agent runtime helper that proxies all tool writes through Argvtix Tool Gateway."""

    def __init__(self, client: ArgvtixClient):
        self.client = client
        self._local_handlers: dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, handler: Callable[..., Any]) -> None:
        """Registers a local tool implementation."""
        self._local_handlers[name] = handler

    def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        order_id: Optional[str] = None,
        amount: Optional[float] = None,
        agent_id: str = "sdk-agent",
    ) -> GatewayExecutionResult:
        """Submits tool invocation to Argvtix Gateway.

        If Gateway returns ALLOW and a local handler exists, executes the handler.
        If Gateway returns BLOCK, immediately aborts without execution.
        If Gateway returns ASK_HUMAN, returns pending approval status.
        """
        response = self.client.call_gateway(
            tool_name=tool_name,
            parameters=parameters,
            order_id=order_id,
            amount=amount,
            agent_id=agent_id,
        )

        decision = response.get("decision", "BLOCK")
        allowed = decision == "ALLOW"
        requires_approval = decision == "ASK_HUMAN"

        result_payload = response.get("tool_result")
        if allowed and not result_payload and tool_name in self._local_handlers:
            # Execute registered local tool handler
            try:
                result_payload = self._local_handlers[tool_name](**parameters)
            except Exception as e:
                result_payload = {"error": str(e)}

        return GatewayExecutionResult(
            tool_name=tool_name,
            decision=decision,
            allowed=allowed,
            result=result_payload if isinstance(result_payload, dict) else {"output": result_payload},
            violation_reason=response.get("reason"),
            approval_id=response.get("approval_id"),
            requires_approval=requires_approval,
        )
