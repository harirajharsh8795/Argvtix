"""
Model Context Protocol (MCP) Server Package.

Exposes the ToolGateway as a standards-compliant MCP server
that Claude Desktop, Cursor, and any MCP-compatible client
can connect to via JSON-RPC 2.0 over stdio or HTTP/SSE.
"""

from argvtix.mcp.schemas import MCPRequest, MCPResponse, MCPToolDefinition
from argvtix.mcp.server import MCPServer

__all__ = ["MCPServer", "MCPRequest", "MCPResponse", "MCPToolDefinition"]
