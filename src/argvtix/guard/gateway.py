"""
Tool Gateway MCP Proxy Module.

Enforcement Boundary between AI Agents and Enterprise Databases.
The AI Agent never holds database credentials or direct write access.
Every tool call passes through this gateway:
1. Validates tool name and arguments.
2. Checks idempotency keys to prevent duplicate execution.
3. Enforces ActionGuard policies BEFORE any execution.
4. If ALLOW -> executes the tool handler and records result.
5. If BLOCK -> returns policy violation error with ZERO database writes.
6. If ASK_HUMAN -> enqueues request in ApprovalQueue with ZERO database writes to business tables.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from argvtix.cache import cache_manager
from argvtix.guard.approvals import ApprovalQueue
from argvtix.guard.engine import ActionGuard, GuardCheckRequest
from argvtix.target_app.tools import shop_tools
from argvtix.trace.schemas import GuardDecision


class GatewayResult(BaseModel):
    """Structured response returned by ToolGateway for every tool call."""

    tool_name: str
    decision: GuardDecision
    success: bool
    status: str = "completed"  # completed, blocked, pending_approval, error
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    policy_rule: str | None = None
    approval_id: str | None = None
    idempotency_key: str | None = None


@dataclass
class ToolRegistration:
    """Registered tool handler metadata."""

    name: str
    handler: Callable[..., Any]
    is_write: bool = True
    description: str = ""


class ToolGateway:
    """
    Control proxy for tool execution with pre-action safety guard enforcement.
    """

    def __init__(
        self,
        guard: ActionGuard | None = None,
        approval_queue: ApprovalQueue | None = None,
    ) -> None:
        self.guard = guard or ActionGuard()
        self.approval_queue = approval_queue or ApprovalQueue()
        self.tools: dict[str, ToolRegistration] = {}
        self._idempotency_cache: dict[str, GatewayResult] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the standard ShopOps tools."""
        self.register_tool("get_order", shop_tools.get_order, is_write=False, description="Read order details")
        self.register_tool("get_customer_balance", shop_tools.get_customer_balance, is_write=False, description="Read customer balance")
        self.register_tool("check_order_refund_status", shop_tools.check_order_refund_status, is_write=False, description="Read refund status")
        self.register_tool("issue_refund", shop_tools.issue_refund, is_write=True, description="Write refund record")
        self.register_tool("cancel_order", shop_tools.cancel_order, is_write=True, description="Write order cancellation")

    def register_tool(
        self,
        name: str,
        handler: Callable[..., Any],
        is_write: bool = True,
        description: str = "",
    ) -> None:
        """Register a new tool handler with write permission flag."""
        self.tools[name] = ToolRegistration(
            name=name,
            handler=handler,
            is_write=is_write,
            description=description,
        )

    def _save_idempotency(self, idempotency_key: str | None, gate_res: GatewayResult) -> None:
        if idempotency_key:
            self._idempotency_cache[idempotency_key] = gate_res
            try:
                cache_manager.set(
                    f"idempotency:{idempotency_key}",
                    gate_res.model_dump(),
                    ttl_seconds=86400,
                )
            except Exception:
                pass

    def call(
        self,
        tool_name: str,
        params: dict[str, Any],
        db: Session,
        agent_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        """
        Main execution method for agent tool invocations.
        Enforces policy guard before write tools execute.
        """
        # 1. Idempotency check: Return cached result if key exists
        if idempotency_key:
            if idempotency_key in self._idempotency_cache:
                return self._idempotency_cache[idempotency_key]
            cached_data = cache_manager.get(f"idempotency:{idempotency_key}")
            if cached_data and isinstance(cached_data, dict):
                res = GatewayResult(**cached_data)
                self._idempotency_cache[idempotency_key] = res
                return res

        # 2. Check tool exists
        if tool_name not in self.tools:
            return GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.BLOCK,
                success=False,
                status="error",
                error=f"Tool '{tool_name}' is not registered in ToolGateway.",
            )

        tool_reg = self.tools[tool_name]

        # 3. Read-only tools bypass Guard evaluation
        if not tool_reg.is_write:
            res = self._execute_handler(tool_reg.handler, params, db)
            gate_res = GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.ALLOW,
                success=res.success if hasattr(res, "success") else True,
                data=res.data if hasattr(res, "data") else (res if isinstance(res, dict) else {}),
                error=res.error if hasattr(res, "error") else None,
                idempotency_key=idempotency_key,
            )
            self._save_idempotency(idempotency_key, gate_res)
            return gate_res

        # 4. Write tools: Evaluate ActionGuard
        guard_req = self._build_guard_request(tool_name, params)
        guard_resp = self.guard.evaluate(guard_req, db)

        # 5. Handle BLOCK: Zero database writes
        if guard_resp.decision == GuardDecision.BLOCK:
            gate_res = GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.BLOCK,
                success=False,
                status="blocked",
                error=guard_resp.reason,
                policy_rule=guard_resp.policy_rule_triggered,
                idempotency_key=idempotency_key,
            )
            self._save_idempotency(idempotency_key, gate_res)
            return gate_res

        # 6. Handle ASK_HUMAN: Zero writes to business tables, enqueue in approval queue
        if guard_resp.decision == GuardDecision.ASK_HUMAN:
            approval = self.approval_queue.enqueue(
                action_type=tool_name,
                tool_name=tool_name,
                entity_id=str(params.get("order_id") or params.get("ticket_id") or "unknown"),
                customer_id=params.get("customer_id"),
                amount=float(params.get("amount", 0.0)),
                payload=params,
                guard_reason=guard_resp.reason,
                risk_level=guard_resp.risk_level,
                idempotency_key=idempotency_key,
                db=db,
            )
            gate_res = GatewayResult(
                tool_name=tool_name,
                decision=GuardDecision.ASK_HUMAN,
                success=False,
                status="pending_approval",
                error=guard_resp.reason,
                approval_id=approval.id,
                policy_rule="human_approval_required",
                idempotency_key=idempotency_key,
            )
            self._save_idempotency(idempotency_key, gate_res)
            return gate_res

        # 7. Handle ALLOW: Execute real tool against database
        tool_res = self._execute_handler(tool_reg.handler, params, db, idempotency_key=idempotency_key)
        gate_res = GatewayResult(
            tool_name=tool_name,
            decision=GuardDecision.ALLOW,
            success=tool_res.success if hasattr(tool_res, "success") else True,
            status="completed",
            data=tool_res.data if hasattr(tool_res, "data") else (tool_res if isinstance(tool_res, dict) else {}),
            error=tool_res.error if hasattr(tool_res, "error") else None,
            idempotency_key=idempotency_key,
        )
        self._save_idempotency(idempotency_key, gate_res)
        return gate_res

    def execute_bypassing_guard(
        self,
        tool_name: str,
        params: dict[str, Any],
        db: Session,
    ) -> Any:
        """
        Executes a tool directly after human approval has been granted.
        Only accessible by ApprovalQueue.
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not registered in gateway.")
        handler = self.tools[tool_name].handler
        return self._execute_handler(handler, params, db)

    def _execute_handler(
        self,
        handler: Callable[..., Any],
        params: dict[str, Any],
        db: Session,
        idempotency_key: str | None = None,
    ) -> Any:
        """Inspects handler parameters and passes db and idempotency_key if expected."""
        sig = inspect.signature(handler)
        kwargs = dict(params)
        if "db" in sig.parameters:
            kwargs["db"] = db
        if "idempotency_key" in sig.parameters and "idempotency_key" not in kwargs:
            kwargs["idempotency_key"] = idempotency_key
        return handler(**kwargs)

    def _build_guard_request(self, tool_name: str, params: dict[str, Any]) -> GuardCheckRequest:
        """Maps arbitrary tool parameters into a standard GuardCheckRequest."""
        order_id = str(params.get("order_id", ""))
        customer_id = str(params.get("customer_id", ""))
        amount = float(params.get("amount", 0.0))
        reason = str(params.get("reason", "agent_tool_call"))

        workflow_type = "refund" if "refund" in tool_name else ("cancel" if "cancel" in tool_name else "general")

        return GuardCheckRequest(
            workflow_type=workflow_type,
            tool_name=tool_name,
            customer_id=customer_id,
            order_id=order_id,
            amount=amount,
            reason=reason,
            metadata=params,
        )
