"""
LLM Model Adapters for Multi-Model Benchmarking.

Each adapter normalises provider-specific APIs to a common interface:
    generate(prompt: str) -> ModelResponse

Supported providers:
  - Gemini (google-generativeai)
  - Claude (anthropic via litellm)
  - GPT-4o (openai via litellm)
  - LiteLLM (any litellm-compatible model string)
  - MockAdapter (zero-cost deterministic testing)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Shared response schema
# ---------------------------------------------------------------------------


@dataclass
class ModelResponse:
    """Normalised response from any LLM provider."""

    text: str
    model_id: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    raw_response: Any = field(default=None, repr=False)
    error: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def succeeded(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ModelAdapter(ABC):
    """Common interface every model adapter must implement."""

    model_id: str = "base"

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        """Send prompt, return normalised ModelResponse."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model_id={self.model_id!r})"


# ---------------------------------------------------------------------------
# Mock adapter (always available, no API keys needed)
# ---------------------------------------------------------------------------


class MockAdapter(ModelAdapter):
    """Deterministic mock for unit tests — returns a fixed-format response."""

    model_id = "mock/deterministic-v1"
    _cost_per_token = 0.0

    def __init__(self, fixed_text: str = "Refund approved for order ORD-001.") -> None:
        self._fixed_text = fixed_text

    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        t0 = time.perf_counter()
        # Simulate ~40 ms
        time.sleep(0.04)
        latency = (time.perf_counter() - t0) * 1000
        tokens = max(1, len(prompt.split()))
        return ModelResponse(
            text=self._fixed_text,
            model_id=self.model_id,
            latency_ms=latency,
            prompt_tokens=tokens,
            completion_tokens=len(self._fixed_text.split()),
            cost_usd=0.0,
        )


# ---------------------------------------------------------------------------
# Gemini adapter
# ---------------------------------------------------------------------------


class GeminiAdapter(ModelAdapter):
    """
    Adapter for Google Gemini models via google-generativeai SDK.

    Default: gemini-1.5-pro-latest
    Pricing (approximate, May 2025):
      - Input:  $3.50 / 1M tokens
      - Output: $10.50 / 1M tokens
    """

    _INPUT_COST_PER_TOKEN = 3.50 / 1_000_000
    _OUTPUT_COST_PER_TOKEN = 10.50 / 1_000_000

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro-latest",
        api_key: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.model_id = f"google/{model_name}"
        self._model_name = model_name
        self._temperature = temperature
        self._client = None
        self._api_key = api_key
        self._init_client()

    def _init_client(self) -> None:
        try:
            import google.generativeai as genai

            if self._api_key:
                genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(
                model_name=self._model_name,
                generation_config={"temperature": self._temperature},
            )
        except ImportError:
            self._client = None  # Will surface error at generate() time

    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        if self._client is None:
            return ModelResponse(
                text="",
                model_id=self.model_id,
                latency_ms=0,
                error="google-generativeai not installed or client init failed",
            )
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            t0 = time.perf_counter()
            response = self._client.generate_content(full_prompt)
            latency = (time.perf_counter() - t0) * 1000

            text = response.text or ""
            # Gemini usage metadata
            usage = getattr(response, "usage_metadata", None)
            prompt_tokens = (
                getattr(usage, "prompt_token_count", len(prompt.split()))
                if usage
                else len(prompt.split())
            )
            completion_tokens = (
                getattr(usage, "candidates_token_count", len(text.split()))
                if usage
                else len(text.split())
            )

            cost = (
                prompt_tokens * self._INPUT_COST_PER_TOKEN
                + completion_tokens * self._OUTPUT_COST_PER_TOKEN
            )

            return ModelResponse(
                text=text,
                model_id=self.model_id,
                latency_ms=latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
                raw_response=response,
            )
        except Exception as exc:
            return ModelResponse(
                text="",
                model_id=self.model_id,
                latency_ms=0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# LiteLLM adapter (covers Claude, GPT-4o, Cohere, Mistral, etc.)
# ---------------------------------------------------------------------------

# Approximate pricing table (USD per token, May 2025)
_LITELLM_PRICING: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet-20241022": (3.00 / 1_000_000, 15.00 / 1_000_000),
    "claude-3-opus-20240229": (15.00 / 1_000_000, 75.00 / 1_000_000),
    "gpt-4o": (5.00 / 1_000_000, 15.00 / 1_000_000),
    "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
    "gpt-4-turbo": (10.00 / 1_000_000, 30.00 / 1_000_000),
    "mistral/mistral-large-latest": (4.00 / 1_000_000, 12.00 / 1_000_000),
}


class LiteLLMAdapter(ModelAdapter):
    """
    Generic adapter for any model supported by litellm.

    model_string examples:
      - "claude-3-5-sonnet-20241022"
      - "gpt-4o"
      - "gpt-4o-mini"
      - "mistral/mistral-large-latest"
      - "ollama/llama3"
    """

    def __init__(
        self,
        model_string: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        self.model_id = model_string
        self._model_string = model_string
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens

        # Pricing lookup (falls back to zero)
        key = model_string.split("/")[-1]
        pricing = _LITELLM_PRICING.get(model_string) or _LITELLM_PRICING.get(key, (0.0, 0.0))
        self._in_cost, self._out_cost = pricing

    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        try:
            import litellm
        except ImportError:
            return ModelResponse(
                text="",
                model_id=self.model_id,
                latency_ms=0,
                error="litellm not installed",
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self._model_string,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key

        try:
            t0 = time.perf_counter()
            response = litellm.completion(**kwargs)  # type: ignore[attr-defined]
            latency = (time.perf_counter() - t0) * 1000

            text = response.choices[0].message.content or ""
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else len(prompt.split())
            completion_tokens = usage.completion_tokens if usage else len(text.split())
            cost = prompt_tokens * self._in_cost + completion_tokens * self._out_cost

            return ModelResponse(
                text=text,
                model_id=self.model_id,
                latency_ms=latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
                raw_response=response,
            )
        except Exception as exc:
            return ModelResponse(
                text="",
                model_id=self.model_id,
                latency_ms=0,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Named convenience subclasses
# ---------------------------------------------------------------------------


class ClaudeAdapter(LiteLLMAdapter):
    """Claude 3.5 Sonnet via LiteLLM."""

    def __init__(self, api_key: str | None = None, temperature: float = 0.0) -> None:
        super().__init__(
            model_string="claude-3-5-sonnet-20241022",
            api_key=api_key,
            temperature=temperature,
        )


class GPT4oAdapter(LiteLLMAdapter):
    """GPT-4o via LiteLLM."""

    def __init__(self, api_key: str | None = None, temperature: float = 0.0) -> None:
        super().__init__(
            model_string="gpt-4o",
            api_key=api_key,
            temperature=temperature,
        )
