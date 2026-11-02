"""
Tests for Model Adapter Layer and Capability Registry (MISSING-02).
"""

from __future__ import annotations

import pytest

from argvtix.target_app.adapters import (
    GeminiAdapter,
    LiteLLMAdapter,
    MockAdapter,
    get_adapter,
)
from argvtix.target_app.capability_registry import (
    ModelCapability,
    ModelMetadata,
    capability_registry,
)
from argvtix.target_app.spend_guard import spend_guard


class TestCapabilityRegistry:
    def test_default_models_registered(self):
        gemini = capability_registry.get("gemini-1.5-pro")
        assert gemini is not None
        assert gemini.provider == "google"
        assert ModelCapability.TOOL_CALLING in gemini.capabilities

        gpt = capability_registry.get("gpt-4o")
        assert gpt is not None
        assert ModelCapability.VISION in gpt.capabilities

    def test_capability_support_and_assertion(self):
        assert (
            capability_registry.supports("gemini-2.0-flash", ModelCapability.TOOL_CALLING) is True
        )

        # Custom model without vision
        capability_registry.register(
            ModelMetadata(
                name="text-only-v1",
                provider="mock",
                capabilities={ModelCapability.STRUCTURED_OUTPUT},
            )
        )
        assert capability_registry.supports("text-only-v1", ModelCapability.VISION) is False

        with pytest.raises(ValueError, match="does not support"):
            capability_registry.assert_supports("text-only-v1", ModelCapability.VISION)

    def test_token_cost_calculation(self):
        # 1,000,000 input tokens on gemini-1.5-pro = $1.25, 1,000,000 output = $5.00
        cost = capability_registry.calculate_cost("gemini-1.5-pro", 1_000_000, 1_000_000)
        assert cost == pytest.approx(6.25, 0.001)


class TestModelAdapters:
    def test_factory_creates_correct_adapter(self):
        a1 = get_adapter("gemini-1.5-pro")
        assert isinstance(a1, GeminiAdapter)

        a2 = get_adapter("gpt-4o")
        assert isinstance(a2, LiteLLMAdapter)

        a3 = get_adapter("mock-llm")
        assert isinstance(a3, MockAdapter)

    def test_mock_adapter_execution(self):
        adapter = MockAdapter()
        res = adapter.call("intent classifier customer ticket: I want to cancel order 101")
        assert "cancel_order" in res

    def test_gemini_adapter_fallback_without_keys(self):
        adapter = GeminiAdapter(api_key=None)
        res = adapter.call("intent classifier customer ticket: refund order 101")
        assert "refund" in res

    def test_adapter_respects_spend_guard(self):
        spend_guard.reset()
        adapter = GeminiAdapter()

        # Artificially set daily cap to 0
        spend_guard.daily_cap_usd = 0.00000001
        res = adapter.call("a very long prompt to exceed tiny cap")
        assert "spend limit reached" in res.lower()
        spend_guard.reset()
