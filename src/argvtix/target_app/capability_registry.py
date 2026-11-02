"""
Model Capability Registry (MISSING-02).

Maintains metadata, capabilities, context limits, and token pricing for LLM models:
- Prevents invoking unsupported capabilities (e.g. tool calling on models lacking function support)
- Provides standard cost calculation per 1M tokens
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, Field


class ModelCapability(str, Enum):
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    VISION = "vision"
    STREAMING = "streaming"
    MULTILINGUAL = "multilingual"


class ModelMetadata(BaseModel):
    """Configuration profile and operational boundaries for an LLM model."""

    name: str
    provider: str  # "google" | "openai" | "anthropic" | "mock"
    context_window: int = 128000
    capabilities: set[ModelCapability] = Field(default_factory=set)
    input_cost_per_million: float = 0.50
    output_cost_per_million: float = 1.50


class ModelCapabilityRegistry:
    """Central registry of approved production and testing LLMs."""

    def __init__(self) -> None:
        self._models: dict[str, ModelMetadata] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults: Sequence[ModelMetadata] = [
            ModelMetadata(
                name="gemini-1.5-pro",
                provider="google",
                context_window=1000000,
                capabilities={
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.VISION,
                    ModelCapability.STREAMING,
                    ModelCapability.MULTILINGUAL,
                },
                input_cost_per_million=1.25,
                output_cost_per_million=5.00,
            ),
            ModelMetadata(
                name="gemini-2.0-flash",
                provider="google",
                context_window=1000000,
                capabilities={
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.STREAMING,
                    ModelCapability.MULTILINGUAL,
                },
                input_cost_per_million=0.10,
                output_cost_per_million=0.40,
            ),
            ModelMetadata(
                name="gpt-4o",
                provider="openai",
                context_window=128000,
                capabilities={
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.VISION,
                    ModelCapability.STREAMING,
                    ModelCapability.MULTILINGUAL,
                },
                input_cost_per_million=2.50,
                output_cost_per_million=10.00,
            ),
            ModelMetadata(
                name="claude-3-5-sonnet",
                provider="anthropic",
                context_window=200000,
                capabilities={
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.VISION,
                    ModelCapability.STREAMING,
                    ModelCapability.MULTILINGUAL,
                },
                input_cost_per_million=3.00,
                output_cost_per_million=15.00,
            ),
            ModelMetadata(
                name="mock-llm",
                provider="mock",
                context_window=32000,
                capabilities={
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.MULTILINGUAL,
                },
                input_cost_per_million=0.0,
                output_cost_per_million=0.0,
            ),
        ]
        for m in defaults:
            self.register(m)

    def register(self, metadata: ModelMetadata) -> None:
        self._models[metadata.name.lower()] = metadata

    def get(self, model_name: str) -> ModelMetadata | None:
        return self._models.get(model_name.lower())

    def supports(self, model_name: str, capability: ModelCapability) -> bool:
        meta = self.get(model_name)
        if not meta:
            return False
        return capability in meta.capabilities

    def assert_supports(self, model_name: str, capability: ModelCapability) -> None:
        if not self.supports(model_name, capability):
            raise ValueError(
                f"Model '{model_name}' does not support required capability '{capability.value}'"
            )

    def calculate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        meta = self.get(model_name)
        if not meta:
            return 0.0
        in_cost = (input_tokens / 1_000_000.0) * meta.input_cost_per_million
        out_cost = (output_tokens / 1_000_000.0) * meta.output_cost_per_million
        return round(in_cost + out_cost, 6)


# Global singleton instance
capability_registry = ModelCapabilityRegistry()
