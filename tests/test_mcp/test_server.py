"""
Tests for ARGVTIX Model Context Protocol (MCP) Server.
Verifies JSON-RPC 2.0 handshake, tool catalogue advertisement, and zero-bypass tool execution.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, Customer, Order, Payment
from argvtix.guard.gateway import ToolGateway
from argvtix.mcp.schemas import MCPErrorCode
from argvtix.mcp.server import MCPServer


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database seeded with baseline ecommerce data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    cust = Customer(
        id="c_mcp", name="Arjun Sharma", email="arjun@example.com", wallet_balance=5000.0
    )
    session.add(cust)

    order1 = Order(id="ord_mcp_1", customer_id="c_mcp", status="delivered", total_amount=1500.0)
    order2 = Order(id="ord_mcp_2", customer_id="c_mcp", status="delivered", total_amount=25000.0)
    session.add_all([order1, order2])

    pay1 = Payment(
        id="pay_mcp_1",
        order_id="ord_mcp_1",
        customer_id="c_mcp",
        amount=1500.0,
        method="upi",
        status="succeeded",
    )
    pay2 = Payment(
        id="pay_mcp_2",
        order_id="ord_mcp_2",
        customer_id="c_mcp",
        amount=25000.0,
        method="card",
        status="succeeded",
    )
    session.add_all([pay1, pay2])

    session.commit()
    yield session
    session.close()


@pytest.fixture
def mcp_server(db_session):
    """Instantiate MCPServer with session_factory pointing to test db."""
    gateway = ToolGateway()
    server = MCPServer(gateway=gateway, session_factory=lambda: db_session)
    return server


class TestMCPServerJSONRPC:
    """JSON-RPC specification and error handling tests."""

    def test_initialize_handshake(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "claude-desktop", "version": "0.1.0"},
                "protocolVersion": "2024-11-05",
            },
        }
        res = mcp_server.handle(req)
        assert res["id"] == 1
        assert "result" in res
        result = res["result"]
        assert result["serverInfo"]["name"] == "argvtix-tool-gateway"
        assert "capabilities" in result
        assert result["capabilities"]["tools"]["listChanged"] is False

    def test_ping_liveness(self, mcp_server):
        req = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
        res = mcp_server.handle(req)
        assert res["id"] == 2
        assert res["result"] == {"status": "pong"}

    def test_invalid_json_rpc_syntax(self, mcp_server):
        req = {"not_a_valid_jsonrpc": True}
        res = mcp_server.handle(req)
        assert "error" in res
        assert res["error"]["code"] == MCPErrorCode.PARSE_ERROR

    def test_unknown_method(self, mcp_server):
        req = {"jsonrpc": "2.0", "id": 3, "method": "unknown_future_method", "params": {}}
        res = mcp_server.handle(req)
        assert "error" in res
        assert res["error"]["code"] == MCPErrorCode.METHOD_NOT_FOUND


class TestMCPToolsCatalogue:
    """Tool discovery and schema verification."""

    def test_list_tools(self, mcp_server):
        req = {"jsonrpc": "2.0", "id": 10, "method": "tools/list"}
        res = mcp_server.handle(req)
        assert res["id"] == 10
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "get_order" in tool_names
        assert "issue_refund" in tool_names
        assert "cancel_order" in tool_names

        issue_refund_tool = next(t for t in tools if t["name"] == "issue_refund")
        schema = issue_refund_tool["inputSchema"]
        assert "order_id" in schema["properties"]
        assert "amount" in schema["properties"]
        assert "order_id" in schema["required"]


class TestMCPToolExecutionWithGuard:
    """Tool execution via ToolGateway enforcing Guard boundaries."""

    def test_read_tool_execution(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "get_order",
                "arguments": {"order_id": "ord_mcp_1"},
            },
        }
        res = mcp_server.handle(req)
        assert res["id"] == 20
        assert "result" in res
        content = res["result"]["content"]
        assert len(content) > 0
        assert "ord_mcp_1" in content[0]["text"]

    def test_write_tool_allowed_refund(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "issue_refund",
                "arguments": {
                    "order_id": "ord_mcp_1",
                    "customer_id": "c_mcp",
                    "amount": 500.0,
                    "reason": "Damaged on delivery",
                },
            },
        }
        res = mcp_server.handle(req)
        assert res["id"] == 21
        assert "result" in res
        assert res["result"]["isError"] is False
        assert "500" in res["result"]["content"][0]["text"]

    def test_write_tool_high_value_asks_human(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "issue_refund",
                "arguments": {
                    "order_id": "ord_mcp_2",
                    "customer_id": "c_mcp",
                    "amount": 15000.0,
                    "reason": "Expensive return",
                },
            },
        }
        res = mcp_server.handle(req)
        assert res["id"] == 22
        assert "result" in res
        assert res["result"]["pendingApproval"] is True
        assert res["result"]["approvalId"] is not None

    def test_write_tool_blocked_excess_refund(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 23,
            "method": "tools/call",
            "params": {
                "name": "issue_refund",
                "arguments": {
                    "order_id": "ord_mcp_1",
                    "customer_id": "c_mcp",
                    "amount": 99999.0,
                    "reason": "Fraudulent claim",
                },
            },
        }
        res = mcp_server.handle(req)
        assert res["id"] == 23
        assert "error" in res
        assert res["error"]["code"] == MCPErrorCode.GUARD_BLOCKED

    def test_call_missing_required_arguments(self, mcp_server):
        req = {
            "jsonrpc": "2.0",
            "id": 24,
            "method": "tools/call",
            "params": {
                "name": "issue_refund",
                "arguments": {},
            },
        }
        res = mcp_server.handle(req)
        assert res["id"] == 24
        assert "error" in res
        assert res["error"]["code"] == MCPErrorCode.GUARD_BLOCKED
