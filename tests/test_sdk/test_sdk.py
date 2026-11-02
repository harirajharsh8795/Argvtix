"""Tests for Argvtix SDK (@trace decorator, client, and tool gateway)."""

import asyncio

import pytest
from argvtix_sdk.client import ArgvtixClient
from argvtix_sdk.gateway import ToolGatewayClient
from argvtix_sdk.trace import local_trace_buffer, trace


class TestSDKTraceDecorator:
    def test_sync_function_auto_instrumentation(self):
        initial_count = len(local_trace_buffer)

        @trace(workflow="test_order_flow", step_type="tool")
        def calculate_discount(price: float, percent: float) -> float:
            return price * (1.0 - percent / 100.0)

        result = calculate_discount(1000.0, 15.0)
        assert result == 850.0

        assert len(local_trace_buffer) == initial_count + 1
        recorded = local_trace_buffer[-1]
        assert recorded["workflow"] == "test_order_flow"
        assert recorded["status"] == "SUCCESS"
        assert recorded["total_latency_ms"] >= 0.0
        assert len(recorded["steps"]) == 1
        assert recorded["steps"][0]["name"] == "calculate_discount"
        assert recorded["steps"][0]["inputs"]["price"] == "1000.0"

    @pytest.mark.asyncio
    async def test_async_function_auto_instrumentation(self):
        initial_count = len(local_trace_buffer)

        @trace(workflow="async_inventory_check", step_type="tool")
        async def fetch_stock(sku: str) -> dict[str, int]:
            await asyncio.sleep(0.01)
            return {"sku": sku, "stock": 42}

        res = await fetch_stock("SKU-999")
        assert res["stock"] == 42

        assert len(local_trace_buffer) == initial_count + 1
        recorded = local_trace_buffer[-1]
        assert recorded["workflow"] == "async_inventory_check"
        assert recorded["status"] == "SUCCESS"

    def test_exception_capture_in_traced_function(self):
        @trace(workflow="error_flow")
        def failing_function():
            raise ValueError("Invalid parameters passed to tool")

        with pytest.raises(ValueError, match="Invalid parameters"):
            failing_function()

        recorded = local_trace_buffer[-1]
        assert recorded["status"] == "ERROR"
        assert "Invalid parameters" in recorded["steps"][0]["error"]


class TestToolGatewayClient:
    def test_gateway_allow_executes_tool_handler(self, monkeypatch: pytest.MonkeyPatch):
        client = ArgvtixClient(api_url="http://mock-argvtix:8000")

        # Mock client.call_gateway returning ALLOW
        monkeypatch.setattr(
            client,
            "call_gateway",
            lambda **kwargs: {"decision": "ALLOW", "tool_result": None},
        )

        gateway = ToolGatewayClient(client=client)
        gateway.register_tool("refund_tool", lambda order_id, amount: {"refunded": amount})

        result = gateway.call_tool(
            tool_name="refund_tool",
            parameters={"order_id": "ORD-1", "amount": 500.0},
        )

        assert result.allowed is True
        assert result.decision == "ALLOW"
        assert result.result == {"refunded": 500.0}

    def test_gateway_block_prevents_execution(self, monkeypatch: pytest.MonkeyPatch):
        client = ArgvtixClient(api_url="http://mock-argvtix:8000")

        monkeypatch.setattr(
            client,
            "call_gateway",
            lambda **kwargs: {
                "decision": "BLOCK",
                "reason": "Order already delivered and return window passed",
            },
        )

        gateway = ToolGatewayClient(client=client)
        called = {"executed": False}

        def mock_handler(**kwargs):
            called["executed"] = True

        gateway.register_tool("cancel_order", mock_handler)

        result = gateway.call_tool(
            tool_name="cancel_order",
            parameters={"order_id": "ORD-DELIVERED"},
        )

        assert result.allowed is False
        assert result.decision == "BLOCK"
        assert called["executed"] is False
        assert "return window passed" in result.violation_reason

    def test_gateway_ask_human_returns_approval_pending(self, monkeypatch: pytest.MonkeyPatch):
        client = ArgvtixClient(api_url="http://mock-argvtix:8000")

        monkeypatch.setattr(
            client,
            "call_gateway",
            lambda **kwargs: {
                "decision": "ASK_HUMAN",
                "approval_id": "APP-999",
                "reason": "Amount ₹25,000 exceeds ₹10,000 auto-approval threshold",
            },
        )

        gateway = ToolGatewayClient(client=client)
        result = gateway.call_tool(
            tool_name="issue_refund",
            parameters={"order_id": "ORD-HIGH", "amount": 25000.0},
        )

        assert result.requires_approval is True
        assert result.approval_id == "APP-999"
        assert result.allowed is False
