"""
Tests for LLM-Based and Deterministic Claim Extraction on Separate Labelled Set.

Verifies:
1. Labelled gold reference set loading (20 cases across en, hi, hinglish).
2. Deterministic parser precision and recall on the separate labelled set.
3. LLM-based extraction path with structured JSON and Pydantic v2 validation.
4. Graceful fallback to deterministic extraction when LLM returns invalid JSON or fails.
5. Strict separation between the claim extraction labelled set and the planted verification set.
"""

from __future__ import annotations

import json
from typing import Any

from argvtix.evals.benchmarks.adapters import ModelAdapter, ModelResponse
from argvtix.evals.claims.extractor import ClaimExtractor
from argvtix.evals.claims.labelled_dataset import LabelledClaimCase, load_labelled_claims
from argvtix.evals.claims.planted_cases import get_planted_cases
from argvtix.evals.claims.schemas import Claim, ClaimType


class StructuredMockClaimAdapter(ModelAdapter):
    """Adapter that outputs valid Pydantic JSON for claim extraction testing."""

    model_id = "mock/claim-extractor-v1"

    def __init__(self, claims_map: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.claims_map = claims_map or {}

    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        claims = self.claims_map.get(prompt)
        if claims is not None:
            json_text = json.dumps({"claims": claims})
        else:
            # Default fallback mock response
            json_text = json.dumps({"claims": []})

        return ModelResponse(
            text=json_text,
            model_id=self.model_id,
            latency_ms=10.0,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(json_text.split()),
            cost_usd=0.0,
        )


class FailingMockAdapter(ModelAdapter):
    """Adapter that simulates network failures or invalid JSON."""

    model_id = "mock/failing-adapter-v1"

    def __init__(self, mode: str = "invalid_json") -> None:
        self.mode = mode

    def generate(self, prompt: str, system_prompt: str = "") -> ModelResponse:
        if self.mode == "error":
            return ModelResponse(
                text="",
                model_id=self.model_id,
                latency_ms=5.0,
                error="RateLimitExceeded",
            )
        return ModelResponse(
            text="Sorry, I cannot return JSON right now: {{{invalid",
            model_id=self.model_id,
            latency_ms=5.0,
        )


class TestLabelledClaimExtraction:
    """Tests evaluating claim extraction accuracy on the separate reference dataset."""

    def test_load_labelled_claims_dataset(self) -> None:
        cases = load_labelled_claims()
        assert len(cases) == 20
        assert all(isinstance(c, LabelledClaimCase) for c in cases)

        # Check domain diversity
        domains = {c.domain for c in cases}
        assert "ecommerce" in domains
        assert "fintech" in domains
        assert "logistics" in domains
        assert "saas" in domains

        # Check language diversity
        languages = {c.language for c in cases}
        assert "en" in languages
        assert "hi" in languages
        assert "hinglish" in languages

    def test_strict_separation_from_planted_cases(self) -> None:
        """Ensures the extraction gold set is strictly separate from the planted verification set."""
        labelled_cases = load_labelled_claims()
        planted = get_planted_cases()

        # Check IDs
        labelled_ids = {c.id for c in labelled_cases}
        planted_ids = {p.scenario_id for p in planted}
        assert labelled_ids.isdisjoint(planted_ids)
        assert all(c.id.startswith("EXTRACT-") for c in labelled_cases)

    def test_deterministic_parser_accuracy_on_labelled_set(self) -> None:
        """Measures precision, recall, and F1 on the independent labelled dataset."""
        extractor = ClaimExtractor()
        cases = load_labelled_claims()

        dataset = [(c.text, c.expected_claims) for c in cases]
        report = extractor.evaluate_dataset(dataset)

        # Assert precision and recall are both >= 90%
        assert report.total_expected_claims >= 15
        assert report.precision >= 0.90, f"Precision was {report.precision}"
        assert report.recall >= 0.90, f"Recall was {report.recall}"
        assert report.f1_score >= 0.90, f"F1 score was {report.f1_score}"
        assert report.false_positives == 0

    def test_llm_adapter_extraction_with_pydantic_validation(self) -> None:
        """Verifies LLM extraction path parses JSON and produces valid Claim Pydantic models."""
        test_text = "Your refund of ₹1200 for order ORD-1042 has been successfully issued."
        claims_data = [
            {
                "source_text": test_text,
                "claim_type": "refund_issued",
                "entity_type": "order",
                "entity_id": "ORD-1042",
                "claimed_status": "completed",
                "claimed_amount": 1200.0,
                "claimed_currency": "INR",
                "is_success_claimed": True,
                "confidence": 0.98,
            }
        ]

        adapter = StructuredMockClaimAdapter(claims_map={test_text: claims_data})
        extractor = ClaimExtractor(adapter=adapter)

        claims = extractor.extract_claims(test_text)
        assert len(claims) == 1
        claim = claims[0]
        assert isinstance(claim, Claim)
        assert claim.claim_type == ClaimType.REFUND_ISSUED
        assert claim.entity_id == "ORD-1042"
        assert claim.claimed_amount == 1200.0
        assert claim.is_success_claimed is True
        assert claim.confidence == 0.98

    def test_llm_fallback_on_invalid_json(self) -> None:
        """When LLM adapter returns non-JSON or broken text, fallback to deterministic extraction."""
        test_text = "Your refund of ₹1200 for order ORD-1042 has been successfully issued."
        failing_adapter = FailingMockAdapter(mode="invalid_json")
        extractor = ClaimExtractor(adapter=failing_adapter)

        # Fallback should extract the refund claim deterministically
        claims = extractor.extract_claims(test_text)
        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.REFUND_ISSUED
        assert claims[0].entity_id == "ORD-1042"
        assert claims[0].claimed_amount == 1200.0

    def test_llm_fallback_on_adapter_error(self) -> None:
        """When LLM adapter encounters an API exception, fallback cleanly to deterministic extraction."""
        test_text = "Order ORD-9901 has been cancelled per your request."
        failing_adapter = FailingMockAdapter(mode="error")
        extractor = ClaimExtractor(adapter=failing_adapter)

        claims = extractor.extract_claims(test_text)
        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.ORDER_CANCELLED
        assert claims[0].entity_id == "ORD-9901"
        assert claims[0].is_success_claimed is True

    def test_llm_callable_interface(self) -> None:
        """Tests that legacy llm_callable parameter also works seamlessly."""
        test_text = "Ticket TKT-404 has been escalated to Tier 2 support."

        def dummy_llm(prompt: str) -> dict[str, Any]:
            return {
                "claims": [
                    {
                        "source_text": prompt,
                        "claim_type": "ticket_escalated",
                        "entity_type": "ticket",
                        "entity_id": "TKT-404",
                        "claimed_status": "escalated",
                        "is_success_claimed": True,
                    }
                ]
            }

        extractor = ClaimExtractor(llm_callable=dummy_llm)
        claims = extractor.extract_claims(test_text)
        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.TICKET_ESCALATED
        assert claims[0].entity_id == "TKT-404"
