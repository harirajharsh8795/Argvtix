"""
Model Adapters Module.
"""

from __future__ import annotations

from argvtix.target_app.adapters.base import LLMAdapter
from argvtix.target_app.adapters.gemini import GeminiAdapter
from argvtix.target_app.adapters.litellm import LiteLLMAdapter
from argvtix.target_app.adapters.mock import MockAdapter


def get_adapter(model_name: str, **kwargs) -> LLMAdapter:
    """Factory creating the appropriate LLM adapter for a given model identifier."""
    m = model_name.lower()
    if "gemini" in m:
        return GeminiAdapter(model_name=model_name, **kwargs)
    if "gpt" in m or "claude" in m:
        return LiteLLMAdapter(model_name=model_name, **kwargs)
    return MockAdapter(model_name="mock-llm", **kwargs)


__all__ = [
    "GeminiAdapter",
    "LLMAdapter",
    "LiteLLMAdapter",
    "MockAdapter",
    "get_adapter",
]
