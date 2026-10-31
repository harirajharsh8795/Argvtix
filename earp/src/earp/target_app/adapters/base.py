"""
Abstract Base LLM Adapter (MISSING-02).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from earp.target_app.capability_registry import ModelCapability, capability_registry


class LLMAdapter(ABC):
    """Abstract base class for all provider LLM adapters."""

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    def call(self, prompt: str) -> str:
        """Executes prompt against the underlying model and returns response text."""
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculates token cost according to model registry pricing."""
        return capability_registry.calculate_cost(self.model_name, input_tokens, output_tokens)

    def supports(self, capability: ModelCapability) -> bool:
        """Checks if model supports specified capability."""
        return capability_registry.supports(self.model_name, capability)
