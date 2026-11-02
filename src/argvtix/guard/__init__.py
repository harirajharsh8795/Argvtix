"""
Guard Package.

Exposes ActionGuard policy engine, ToolGateway MCP proxy enforcement boundary,
and Human-in-the-Loop ApprovalQueue.
"""

from argvtix.guard.approvals import (
    ApprovalDecisionRequest,
    ApprovalEditRequest,
    ApprovalItemResponse,
    ApprovalQueue,
)
from argvtix.guard.engine import ActionGuard, GuardCheckRequest, GuardCheckResponse
from argvtix.guard.gateway import GatewayResult, ToolGateway, ToolRegistration

__all__ = [
    "ActionGuard",
    "ApprovalDecisionRequest",
    "ApprovalEditRequest",
    "ApprovalItemResponse",
    "ApprovalQueue",
    "GatewayResult",
    "GuardCheckRequest",
    "GuardCheckResponse",
    "ToolGateway",
    "ToolRegistration",
]
