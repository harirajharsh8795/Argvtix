"""
Mock LLM Adapter (MISSING-02).
"""
from __future__ import annotations

from argvtix.target_app.adapters.base import LLMAdapter
from argvtix.target_app.llm import MockLLM


class MockAdapter(LLMAdapter):
    """Deterministic Mock LLM adapter for unit tests and local simulation."""

    def __init__(
        self,
        model_name: str = "mock-llm",
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, max_tokens=max_tokens)
        self._mock = MockLLM()

    def call(self, prompt: str) -> str:
        return self._mock.call(prompt)
