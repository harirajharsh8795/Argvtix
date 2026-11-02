"""
LiteLLM Universal Fallback Adapter (MISSING-02).
"""
from __future__ import annotations

import logging

from argvtix.target_app.adapters.base import LLMAdapter
from argvtix.target_app.adapters.mock import MockAdapter
from argvtix.target_app.spend_guard import spend_guard

logger = logging.getLogger("argvtix.adapters.litellm")


class LiteLLMAdapter(LLMAdapter):
    """LiteLLM universal adapter for GPT-4o, Claude 3.5 Sonnet, etc."""

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, max_tokens=max_tokens)
        self._fallback_mock = MockAdapter(model_name="mock-llm")

    def call(self, prompt: str) -> str:
        est_cost = self.estimate_cost(input_tokens=len(prompt) // 4, output_tokens=256)
        if not spend_guard.check_and_record(est_cost):
            return "Apologies, operation spend limit reached. Please contact system administrator."

        try:
            import litellm
            response = litellm.completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.info("[LITELLM_ADAPTER] LiteLLM call delegated or unconfigured (%s). Using fallback mock.", e)
            return self._fallback_mock.call(prompt)
