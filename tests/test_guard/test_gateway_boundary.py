"""
Unit & Integration Tests for Tool Gateway Boundary Enforcement (Step 4 Item 12).

Validates:
1. Architectural Isolation: The agent module `argvtix.target_app.agent` NEVER imports `shop_tools`.
2. DB Independence: `ShopOpsAgent` can instantiate and execute completely without holding a DB session.
3. Transport Boundary: `ToolGatewayClient` operates over MCP and HTTP proxies.
4. Zero-Bypass Guarantee: A write action CANNOT happen without passing through the Guard:
   - Case 1: When Guard says BLOCK -> Gateway blocks execution, zero database writes occur.
   - Case 2: When Guard says ASK_HUMAN -> Gateway enqueues in ApprovalQueue, zero business table writes occur.
   - Case 3: When Guard says ALLOW -> Gateway allows execution and records row in database.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import ApprovalQueueRecord, Base, Customer, Order, Payment, Product, Refund
from argvtix.gateway.app import app
from argvtix.guard.approvals import ApprovalQueue
from argvtix.guard.client import ToolGatewayClient
from argvtix.guard.gateway import GatewayResult, ToolGateway
from argvtix.mcp.server import MCPServer
from argvtix.target_app.agent import ShopOpsAgent
from argvtix.target_app.llm import MockLLM
from argvtix.trace.schemas import GuardDecision


@pytest.fixture()
def gateway_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    c = Customer(id="1", name="Aarav Gupta", email="aarav@example.com", phone="9876543210")
    session.add(c)

    p = Product(id="1", sku="SKU-001", title="BoAt Headphones", price=1200.0, inventory_count=20)
    session.add(p)

    o = Order(id="1", customer_id="1", status="delivered", total_amount=1200.0)
    session.add(o)

    pay = Payment(
        id="1", order_id="1", customer_id="1", amount=1200.0, method="upi", status="succeeded"
    )
    session.add(pay)
    session.commit()

    yield session
    session.close()


class TestAgentProcessIsolation:
    """Verifies architectural boundary: agent code does not import shop_tools or require raw DB."""

    def test_agent_file_never_imports_shop_tools(self) -> None:
        """AST analysis proves agent.py never imports from argvtix.target_app.tools.shop_tools."""
        agent_path = (
            Path(__file__).resolve().parents[2] / "src" / "argvtix" / "target_app" / "agent.py"
        )
        assert agent_path.exists(), f"agent.py not found at {agent_path}"

        with open(agent_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(agent_path))

        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)

        # Assert no import of shop_tools
        assert not any("shop_tools" in mod for mod in imported_modules), (
            f"Isolation violation: agent.py imports shop_tools: {imported_modules}"
        )

    def test_agent_executes_without_db_session(self) -> None:
        """ShopOpsAgent can run with db=None, using ToolGatewayClient with stubbed tools."""
        stubbed_tools = {
            "get_order": {"order_id": 1, "status": "delivered", "total_amount": 1200.0},
            "issue_refund": {"refund_id": "ref-stub-001", "status": "completed", "amount": 1200.0},
        }
        client = ToolGatewayClient(stubbed_tools=stubbed_tools)
        agent = ShopOpsAgent(gateway_client=client, llm=MockLLM(), db=None)

        result = agent.run(ticket_text="Order 1 ka refund chahiye", customer_id=1)
        assert result.intent == "refund"
        assert result.response != ""
        assert result.trace is not None


class TestToolGatewayTransports:
    """Tests ToolGatewayClient communication across MCP and boundary modes."""

    def test_mcp_transport_tool_execution(self, gateway_db) -> None:
        """ToolGatewayClient invokes tools over MCP protocol with Guard enforcement."""
        mcp = MCPServer(session_factory=lambda: gateway_db)
        client = ToolGatewayClient(mcp_server=mcp)

        # 1. Read-only tool via MCP
        res = client.call_tool("get_order", {"order_id": "1"})
        assert res.success is True
        assert res.decision == GuardDecision.ALLOW
        assert res.data.get("order_id") == 1 or str(res.data.get("order_id")) == "1"

        # 2. Blocked write via MCP (unauthorized customer)
        res_blocked = client.call_tool(
            "issue_refund",
            {"order_id": "1", "customer_id": "999", "amount": 1200.0},
        )
        assert res_blocked.decision == GuardDecision.BLOCK
        assert res_blocked.success is False

    def test_fastapi_http_gateway_endpoint(self, gateway_db) -> None:
        """The /api/v1/guard/gateway/call HTTP endpoint exposes ToolGateway to external agents."""
        from argvtix.db.session import get_db
        from argvtix.security.auth import Role, create_access_token

        app.dependency_overrides[get_db] = lambda: gateway_db
        token = create_access_token(user_id="operator_user", role=Role.OPERATOR)
        test_client = TestClient(app)

        try:
            resp = test_client.post(
                "/api/v1/guard/gateway/call",
                json={"tool_name": "get_order", "params": {"order_id": "1"}},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["tool_name"] == "get_order"
            assert data["decision"] == "allow"
            assert data["success"] is True
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestZeroBypassGuardEnforcement:
    """Proves that a write action cannot happen without passing through the Guard."""

    def test_guard_block_prevents_database_write(self, gateway_db) -> None:
        """When ActionGuard issues a BLOCK decision, zero rows are written to the database."""
        initial_refunds = gateway_db.query(Refund).count()

        # Fraudulent attempt: customer 99 attempting to refund order 1 owned by customer 1
        gateway = ToolGateway()
        res: GatewayResult = gateway.call(
            tool_name="issue_refund",
            params={"order_id": "1", "customer_id": "99", "amount": 1200.0},
            db=gateway_db,
        )

        assert res.decision == GuardDecision.BLOCK
        assert res.success is False
        assert res.status == "blocked"
        assert "mismatch" in res.error.lower() or "not own" in res.error.lower()

        # ZERO database writes verified
        final_refunds = gateway_db.query(Refund).count()
        assert final_refunds == initial_refunds

    def test_guard_ask_human_enqueues_with_zero_business_writes(self, gateway_db) -> None:
        """When ActionGuard flags high amount for human review, zero business rows are written."""
        initial_refunds = gateway_db.query(Refund).count()
        initial_approvals = gateway_db.query(ApprovalQueueRecord).count()

        # Update order total and payment to high amount >= 10000 to trigger human approval threshold
        order = gateway_db.query(Order).filter_by(id="1").first()
        order.total_amount = 12000.0
        payment = gateway_db.query(Payment).filter_by(order_id="1").first()
        payment.amount = 12000.0
        gateway_db.commit()

        queue = ApprovalQueue()
        gateway = ToolGateway(approval_queue=queue)

        res: GatewayResult = gateway.call(
            tool_name="issue_refund",
            params={"order_id": "1", "customer_id": "1", "amount": 12000.0},
            db=gateway_db,
        )

        assert res.decision == GuardDecision.ASK_HUMAN
        assert res.success is False
        assert res.status == "pending_approval"
        assert res.approval_id is not None

        # ZERO writes to Refund business table
        final_refunds = gateway_db.query(Refund).count()
        assert final_refunds == initial_refunds

        # Exactly ONE request enqueued in ApprovalQueue audit table
        final_approvals = gateway_db.query(ApprovalQueueRecord).count()
        assert final_approvals == initial_approvals + 1

    def test_guard_allow_executes_write(self, gateway_db) -> None:
        """When ActionGuard validates and permits an action, write is executed."""
        initial_refunds = gateway_db.query(Refund).count()

        gateway = ToolGateway()
        res: GatewayResult = gateway.call(
            tool_name="issue_refund",
            params={"order_id": "1", "customer_id": "1", "amount": 500.0},
            db=gateway_db,
        )

        assert res.decision == GuardDecision.ALLOW
        assert res.success is True
        assert res.status == "completed"

        # Exactly ONE refund recorded
        final_refunds = gateway_db.query(Refund).count()
        assert final_refunds == initial_refunds + 1

    def test_unregistered_tool_fails_closed(self, gateway_db) -> None:
        """Attempting to invoke an unregistered or arbitrary tool fails closed."""
        gateway = ToolGateway()
        res = gateway.call(
            tool_name="drop_database",
            params={},
            db=gateway_db,
        )
        assert res.decision == GuardDecision.BLOCK
        assert res.success is False
        assert "not registered" in res.error
