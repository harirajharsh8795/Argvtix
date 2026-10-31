"""LLM abstraction — real Gemini or deterministic MockLLM for testing."""
from __future__ import annotations

import json
import os
import re
from typing import Protocol


class LLMProtocol(Protocol):
    """Any object with a .call(prompt) -> str method qualifies as an LLM."""
    def call(self, prompt: str) -> str: ...


class MockLLM:
    """
    Deterministic mock LLM used in tests (no API key needed).
    Parses intent keywords from the prompt and returns realistic JSON responses.
    """

    def call(self, prompt: str) -> str:  # noqa: PLR0911
        p = prompt.lower()

        # --- Classify node ----
        if "intent classifier" in p or "classify the following" in p:
            ticket_part = p.split("customer ticket:")[-1] if "customer ticket:" in p else p

            if "cancel" in ticket_part:
                order_match = re.search(r"order[_\s#]?(\d+)", ticket_part)
                order_id = order_match.group(1) if order_match else "1"
                return json.dumps({
                    "intent": "cancel_order",
                    "order_id": int(order_id),
                    "amount": None,
                    "confidence": 0.92,
                })
            if "balance" in ticket_part or "wallet" in ticket_part:
                return json.dumps({
                    "intent": "balance_inquiry",
                    "order_id": None,
                    "amount": None,
                    "confidence": 0.98,
                })
            if "inventory" in ticket_part or "stock" in ticket_part:
                return json.dumps({
                    "intent": "inventory_check",
                    "order_id": None,
                    "amount": None,
                    "confidence": 0.90,
                })
            if "refund" in ticket_part:
                order_match = re.search(r"order[_\s#]?(\d+)", ticket_part)
                order_id = order_match.group(1) if order_match else "1"
                return json.dumps({
                    "intent": "refund",
                    "order_id": int(order_id),
                    "amount": None,
                    "confidence": 0.95,
                })
            # Default unknown
            return json.dumps({
                "intent": "unknown",
                "order_id": None,
                "amount": None,
                "confidence": 0.3,
            })

        # --- Response generation node ---
        if "generate" in p or "response" in p or "customer" in p:
            if "refund" in p and "approved" in p:
                return "Aapka refund request approve ho gaya hai. 5-7 business days mein amount aapke account mein aa jayega."
            if "refund" in p and ("block" in p or "denied" in p):
                return "Sorry, is order ka refund pehle se process ho chuka hai ya eligibility criteria meet nahi karte."
            if "refund" in p and "human" in p:
                return "Aapki refund request Rs 10,000 se zyada hai. Isse supervisor ke paas approval ke liye bheja gaya hai. Aapko 30 minute mein update milega."
            if "cancel" in p:
                return "Aapka order successfully cancel kar diya gaya hai. Refund 5-7 din mein aa jayega."
            if "balance" in p:
                return "Aapka wallet balance abhi check kar liya gaya hai."
            return "Aapki request process kar di gayi hai. Koi aur madad chahiye?"

        return "Request processed."


class GeminiLLM:
    """
    Thin wrapper around Google Gemini (requires GEMINI_API_KEY env var).
    Falls back to MockLLM if API key is not set.
    """

    def __init__(self, model: str = "gemini-2.0-flash") -> None:
        self.model = model
        self._client = None
        self._use_mock = False

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self._use_mock = True
            self._mock = MockLLM()
            return

        try:
            import google.generativeai as genai  # type: ignore[import]
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(model)
        except ImportError:
            self._use_mock = True
            self._mock = MockLLM()

    def call(self, prompt: str) -> str:
        if self._use_mock:
            return self._mock.call(prompt)
        response = self._client.generate_content(prompt)
        return response.text


def get_default_llm() -> LLMProtocol:
    """Factory — returns GeminiLLM (auto-falls-back to Mock if no key)."""
    return GeminiLLM()
