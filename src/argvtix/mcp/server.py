"""
MCP Server — Tool Gateway as a Model Context Protocol Server.

Implements the MCP specification over two transports:
  1. stdio  — for Claude Desktop / Cursor (process-based)
  2. HTTP/SSE — for web-based MCP clients (FastAPI endpoint)

Supported MCP methods:
  - initialize          : Handshake and capability negotiation
  - tools/list          : Advertise available ToolGateway tools
  - tools/call          : Execute a tool via ToolGateway (with Guard enforcement)
  - ping                : Liveness check

Zero-bypass guarantee: every tools/call passes through ToolGateway.call(),
which enforces ActionGuard before any write operation.

Usage (stdio — Claude Desktop):
    python -m argvtix.mcp.server --transport stdio

Usage (HTTP — web clients):
    python -m argvtix.mcp.server --transport http --port 8765
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from argvtix.db.session import SessionLocal, init_db
from argvtix.guard.gateway import GatewayResult, ToolGateway
from argvtix.mcp.schemas import (
    MCPError,
    MCPErrorCode,
    MCPParameterSchema,
    MCPRequest,
    MCPResponse,
    MCPToolDefinition,
)
from argvtix.trace.schemas import GuardDecision


# ---------------------------------------------------------------------------
# Tool catalogue (synced to ToolGateway registered tools)
# ---------------------------------------------------------------------------

_TOOL_CATALOGUE: list[MCPToolDefinition] = [
    MCPToolDefinition(
        name="get_order",
        description="Read order details by order ID.",
        parameters={
            "order_id": MCPParameterSchema(type="string", description="Order ID", required=True),
        },
        is_write=False,
        requires_guard=False,
    ),
    MCPToolDefinition(
        name="get_customer_balance",
        description="Read customer wallet balance.",
        parameters={
            "customer_id": MCPParameterSchema(type="string", description="Customer ID", required=True),
        },
        is_write=False,
        requires_guard=False,
    ),
    MCPToolDefinition(
        name="check_order_refund_status",
        description="Check refund status for an order.",
        parameters={
            "order_id": MCPParameterSchema(type="string", description="Order ID", required=True),
        },
        is_write=False,
        requires_guard=False,
    ),
    MCPToolDefinition(
        name="issue_refund",
        description="Issue a refund for an order. Requires ActionGuard approval for large amounts.",
        parameters={
            "order_id":    MCPParameterSchema(type="string", description="Order ID",    required=True),
            "customer_id": MCPParameterSchema(type="string", description="Customer ID", required=True),
            "amount":      MCPParameterSchema(type="number", description="Refund amount in INR", required=True),
            "reason":      MCPParameterSchema(type="string", description="Refund reason"),
        },
        is_write=True,
        requires_guard=True,
    ),
    MCPToolDefinition(
        name="cancel_order",
        description="Cancel an order. Requires ActionGuard approval.",
        parameters={
            "order_id":    MCPParameterSchema(type="string", description="Order ID",    required=True),
            "customer_id": MCPParameterSchema(type="string", description="Customer ID", required=True),
            "reason":      MCPParameterSchema(type="string", description="Cancel reason"),
        },
        is_write=True,
        requires_guard=True,
    ),
]

_TOOL_BY_NAME: dict[str, MCPToolDefinition] = {t.name: t for t in _TOOL_CATALOGUE}


# ---------------------------------------------------------------------------
# MCP Server core
# ---------------------------------------------------------------------------

class MCPServer:
    """
    MCP-compliant wrapper around ToolGateway.

    Handles JSON-RPC dispatch and translates GatewayResult
    into standard MCP responses.
    """

    SERVER_NAME = "argvtix-tool-gateway"
    SERVER_VERSION = "1.0.0"
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(
        self,
        gateway: ToolGateway | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self._gateway = gateway or ToolGateway()
        self._session_factory = session_factory or SessionLocal
        init_db()

    def _get_db(self):
        return self._session_factory()

    # ------------------------------------------------------------------
    # Public dispatch entrypoint
    # ------------------------------------------------------------------

    def handle(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse a JSON-RPC request dict and return a JSON-RPC response dict."""
        try:
            req = MCPRequest.model_validate(raw)
        except Exception as exc:
            return MCPResponse.err(
                raw.get("id"),
                MCPErrorCode.PARSE_ERROR,
                f"Parse error: {exc}",
            ).model_dump(exclude_none=True)

        method = req.method
        if method == "initialize":
            resp = self._handle_initialize(req)
        elif method == "tools/list":
            resp = self._handle_tools_list(req)
        elif method == "tools/call":
            resp = self._handle_tools_call(req)
        elif method == "ping":
            resp = MCPResponse.ok(req.id, {"status": "pong"})
        else:
            resp = MCPResponse.err(
                req.id,
                MCPErrorCode.METHOD_NOT_FOUND,
                f"Unknown method: {method!r}",
            )

        return resp.model_dump(exclude_none=True)

    # ------------------------------------------------------------------
    # Method handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, req: MCPRequest) -> MCPResponse:
        return MCPResponse.ok(req.id, {
            "protocolVersion": self.PROTOCOL_VERSION,
            "serverInfo": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION,
            },
            "capabilities": {
                "tools": {"listChanged": False},
            },
        })

    def _handle_tools_list(self, req: MCPRequest) -> MCPResponse:
        tools_payload = []
        for tool in _TOOL_CATALOGUE:
            input_schema = {
                "type": "object",
                "properties": {
                    k: {"type": v.type, "description": v.description}
                    for k, v in tool.parameters.items()
                },
                "required": [k for k, v in tool.parameters.items() if v.required],
            }
            tools_payload.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": input_schema,
                "annotations": {
                    "isWrite": tool.is_write,
                    "requiresGuard": tool.requires_guard,
                },
            })
        return MCPResponse.ok(req.id, {"tools": tools_payload})

    def _handle_tools_call(self, req: MCPRequest) -> MCPResponse:
        tool_name = req.params.get("name", "")
        arguments: dict[str, Any] = req.params.get("arguments", {})

        if tool_name not in _TOOL_BY_NAME:
            return MCPResponse.err(
                req.id,
                MCPErrorCode.TOOL_NOT_FOUND,
                f"Tool '{tool_name}' not found.",
            )

        db = self._get_db()
        try:
            result: GatewayResult = self._gateway.call(
                tool_name=tool_name,
                params=arguments,
                db=db,
                agent_id="mcp-client",
            )
        finally:
            db.close()

        return self._gateway_result_to_mcp(req.id, result)

    def _gateway_result_to_mcp(
        self, request_id: Any, result: GatewayResult
    ) -> MCPResponse:
        """Map GatewayResult -> MCP response."""
        if result.decision == GuardDecision.BLOCK:
            return MCPResponse.err(
                request_id,
                MCPErrorCode.GUARD_BLOCKED,
                result.error or "Action blocked by ActionGuard.",
            )

        if result.decision == GuardDecision.ASK_HUMAN:
            return MCPResponse.ok(request_id, {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Action queued for human review.\n"
                            f"Approval ID: {result.approval_id}\n"
                            f"Reason: {result.error}"
                        ),
                    }
                ],
                "isError": False,
                "pendingApproval": True,
                "approvalId": result.approval_id,
            })

        # ALLOW
        if not result.success:
            return MCPResponse.err(
                request_id,
                MCPErrorCode.TOOL_EXECUTION_ERROR,
                result.error or "Tool execution failed.",
            )

        return MCPResponse.ok(request_id, {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result.data, indent=2, default=str),
                }
            ],
            "isError": False,
        })


# ---------------------------------------------------------------------------
# Stdio transport (Claude Desktop / Cursor)
# ---------------------------------------------------------------------------

class StdioTransport:
    """
    Runs the MCP server over stdin/stdout (newline-delimited JSON).
    This is the transport used by Claude Desktop and Cursor.
    """

    def __init__(self, server: MCPServer) -> None:
        self._server = server

    def run(self) -> None:
        print("[MCP] Argvtix Tool Gateway MCP Server ready (stdio)", file=sys.stderr)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                response = self._server.handle(raw)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError as exc:
                error_resp = MCPResponse.err(None, MCPErrorCode.PARSE_ERROR, str(exc))
                sys.stdout.write(error_resp.model_dump_json() + "\n")
                sys.stdout.flush()


# ---------------------------------------------------------------------------
# HTTP/SSE transport (FastAPI)
# ---------------------------------------------------------------------------

def create_http_app(server: MCPServer):  # type: ignore[return]
    """Return a FastAPI app exposing the MCP server over HTTP."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
    except ImportError:
        raise RuntimeError("fastapi required for HTTP transport. pip install fastapi uvicorn")

    app = FastAPI(
        title="Argvtix Tool Gateway MCP Server",
        description="MCP-compliant HTTP endpoint wrapping the ToolGateway.",
        version=MCPServer.SERVER_VERSION,
    )

    @app.post("/mcp")
    async def mcp_endpoint(request: Request) -> JSONResponse:
        raw = await request.json()
        response = server.handle(raw)
        return JSONResponse(content=response)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "server": MCPServer.SERVER_NAME})

    @app.get("/tools")
    async def list_tools() -> JSONResponse:
        """Convenience REST endpoint that returns tool list (no JSON-RPC wrapper)."""
        req_dict = {"jsonrpc": "2.0", "id": "rest-list", "method": "tools/list", "params": {}}
        resp = server.handle(req_dict)
        return JSONResponse(resp.get("result", {}))

    return app


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Argvtix Tool Gateway MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: 'stdio' for Claude Desktop/Cursor, 'http' for web clients",
    )
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)")
    args = parser.parse_args()

    server = MCPServer()

    if args.transport == "stdio":
        StdioTransport(server).run()
    else:
        try:
            import uvicorn
        except ImportError:
            print("[ERROR] uvicorn required: pip install uvicorn", file=sys.stderr)
            sys.exit(1)

        app = create_http_app(server)
        print(f"[MCP] HTTP server starting on http://{args.host}:{args.port}", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
