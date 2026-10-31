"""
Google Gemini LLM Adapter (MISSING-02).
"""
from __future__ import annotations

import logging
import os

from earp.target_app.adapters.base import LLMAdapter
from earp.target_app.adapters.mock import MockAdapter
from earp.target_app.spend_guard import spend_guard

logger = logging.getLogger("earp.adapters.gemini")


class GeminiAdapter(LLMAdapter):
    """Google Gemini production adapter with spend cap protection."""

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro",
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        super().__init__(model_name=model_name, temperature=temperature, max_tokens=max_tokens)
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._fallback_mock = MockAdapter(model_name="mock-llm")

    def call(self, prompt: str) -> str:
        # Pre-call spend guard check
        est_cost = self.estimate_cost(input_tokens=len(prompt) // 4, output_tokens=256)
        if not spend_guard.check_and_record(est_cost):
            return "Apologies, operation spend limit reached. Please contact system administrator."

        if not self.api_key:
            logger.info("[GEMINI_ADAPTER] GEMINI_API_KEY not found in environment. Gracefully delegating to MockAdapter.")
            return self._fallback_mock.call(prompt)

        try:
            # If google-genai or google.generativeai is installed
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            return response.text or ""
        except Exception as e:
            logger.warning("[GEMINI_ADAPTER_ERROR] Direct Gemini call failed (%s). Falling back to mock.", e)
            return self._fallback_mock.call(prompt)
