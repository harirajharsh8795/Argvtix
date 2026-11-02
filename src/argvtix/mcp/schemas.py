"""
MCP (Model Context Protocol) Data Schemas.

Implements the JSON-RPC 2.0 message envelope required by MCP,
plus typed schemas for tool definitions and results.

Spec reference: https://spec.modelcontextprotocol.io
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 envelope
# ---------------------------------------------------------------------------

class MCPRequest(BaseModel):
    """Incoming JSON-RPC 2.0 request from an MCP client."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class MCPError(BaseModel):
    code: int
    message: str
    data: Any = None


class MCPResponse(BaseModel):
    """Outgoing JSON-RPC 2.0 response."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: dict[str, Any] | None = None
    error: MCPError | None = None

    @classmethod
    def ok(cls, request_id: str | int | None, result: dict[str, Any]) -> "MCPResponse":
        return cls(id=request_id, result=result)

    @classmethod
    def err(cls, request_id: str | int | None, code: int, message: str) -> "MCPResponse":
        return cls(id=request_id, error=MCPError(code=code, message=message))


# ---------------------------------------------------------------------------
# MCP Tool Definition (what the server advertises to clients)
# ---------------------------------------------------------------------------

class MCPParameterSchema(BaseModel):
    type: str = "string"
    description: str = ""
    required: bool = False


class MCPToolDefinition(BaseModel):
    """Describes one callable tool for the MCP tool-listing endpoint."""
    name: str
    description: str
    parameters: dict[str, MCPParameterSchema] = Field(default_factory=dict)
    is_write: bool = True
    requires_guard: bool = True


# ---------------------------------------------------------------------------
# Well-known MCP error codes
# ---------------------------------------------------------------------------

class MCPErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TOOL_NOT_FOUND = -32001
    GUARD_BLOCKED = -32002
    PENDING_APPROVAL = -32003
    TOOL_EXECUTION_ERROR = -32004
