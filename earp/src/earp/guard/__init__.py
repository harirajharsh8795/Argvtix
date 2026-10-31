"""
Guard Package.

Exposes ActionGuard policy engine, ToolGateway MCP proxy enforcement boundary,
and Human-in-the-Loop ApprovalQueue.
"""

from earp.guard.approvals import (
    ApprovalDecisionRequest,
    ApprovalEditRequest,
    ApprovalItemResponse,
    ApprovalQueue,
)
from earp.guard.engine import ActionGuard, GuardCheckRequest, GuardCheckResponse
from earp.guard.gateway import GatewayResult, ToolGateway, ToolRegistration

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
