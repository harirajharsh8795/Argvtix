"""
Tests for Claim-vs-State Verifier and Structured Extraction.

Validates:
1. Extraction accuracy metrics (Precision, Recall, F1).
2. Multilingual extraction (English, Hindi, Hinglish).
3. All 30 planted failure scenarios (6 categories x 5 cases each):
   - FALSE_SUCCESS
   - FALSE_FAILURE
   - OMITTED_FAILURE
   - WRONG_ENTITY
   - PARTIAL_SUCCESS
   - STATUS_MISMATCH
4. Truthful / VERIFIED scenarios.
5. EntityStateSnapshot auto-generation from tool logs.
"""

from __future__ import annotations

import pytest

from argvtix.evals.claims.extractor import ClaimExtractor
from argvtix.evals.claims.planted_cases import get_planted_cases
from argvtix.evals.claims.schemas import (
    Claim,
    ClaimType,
    ClaimVerdict,
)
from argvtix.evals.claims.verifier import ClaimVerifier


class TestClaimExtractor:
    """Tests for structured claim extraction."""

    def setup_method(self) -> None:
        self.extractor = ClaimExtractor()

    def test_extract_english_refund_claim(self) -> None:
        text = "Your refund of ₹1200 for order ORD-1042 has been successfully issued."
        claims = self.extractor.extract_claims(text)
        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.REFUND_ISSUED
        assert claim.entity_id == "ORD-1042"
        assert claim.claimed_amount == 1200.0
        assert claim.is_success_claimed is True

    def test_extract_hinglish_refund_claim(self) -> None:
        text = "Chinta mat kijiye, order ORD-8891 ka 500 rupaye refund initiate ho gaya hai."
        claims = self.extractor.extract_claims(text)
        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.REFUND_ISSUED
        assert claim.entity_id == "ORD-8891"
        assert claim.claimed_amount == 500.0
        assert claim.is_success_claimed is True

    def test_extract_hindi_cancel_claim(self) -> None:
        text = "आपका ऑर्डर ORD-5501 सफलतापूर्वक रद्द कर दिया गया है।"
        claims = self.extractor.extract_claims(text)
        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.ORDER_CANCELLED
        assert claim.entity_id == "ORD-5501"
        assert claim.is_success_claimed is True

    def test_pleasantry_filtered_out(self) -> None:
        text = "Thank you for contacting customer support. Have a wonderful day ahead!"
        claims = self.extractor.extract_claims(text)
        assert len(claims) == 0

    def test_extraction_accuracy_calculation(self) -> None:
        gt = [
            Claim(
                source_text="Your refund of 500 has been issued",
                claim_type=ClaimType.REFUND_ISSUED,
                entity_type="order",
                entity_id="ORD-1042",
                claimed_amount=500.0,
                is_success_claimed=True,
            )
        ]
        extracted = [
            Claim(
                source_text="Your refund of 500 has been issued",
                claim_type=ClaimType.REFUND_ISSUED,
                entity_type="order",
                entity_id="ORD-1042",
                claimed_amount=500.0,
                is_success_claimed=True,
            )
        ]
        report = self.extractor.evaluate_extraction_accuracy(extracted, gt)
        assert report.precision == 1.0
        assert report.recall == 1.0
        assert report.f1_score == 1.0
        assert report.true_positives == 1
        assert report.false_positives == 0
        assert report.false_negatives == 0


class TestClaimVerifierPlantedCases:
    """Verifies all 30 planted cases and 5 verified cases."""

    def setup_method(self) -> None:
        self.verifier = ClaimVerifier()

    @pytest.mark.parametrize("scenario", get_planted_cases(ClaimVerdict.FALSE_SUCCESS))
    def test_false_success_detected(self, scenario) -> None:
        report = self.verifier.verify(
            agent_response=scenario.agent_response,
            tool_records=scenario.tool_records,
        )
        assert report.violations_count >= 1
        verdicts = [r.verdict for r in report.results]
        assert ClaimVerdict.FALSE_SUCCESS in verdicts

    @pytest.mark.parametrize("scenario", get_planted_cases(ClaimVerdict.FALSE_FAILURE))
    def test_false_failure_detected(self, scenario) -> None:
        report = self.verifier.verify(
            agent_response=scenario.agent_response,
            tool_records=scenario.tool_records,
        )
        assert report.violations_count >= 1
        verdicts = [r.verdict for r in report.results]
        assert ClaimVerdict.FALSE_FAILURE in verdicts

    @pytest.mark.parametrize("scenario", get_planted_cases(ClaimVerdict.OMITTED_FAILURE))
    def test_omitted_failure_detected(self, scenario) -> None:
        report = self.verifier.verify(
            agent_response=scenario.agent_response,
            tool_records=scenario.tool_records,
        )
        assert report.violations_count >= 1
        verdicts = [r.verdict for r in report.results]
        assert ClaimVerdict.OMITTED_FAILURE in verdicts

    @pytest.mark.parametrize("scenario", get_planted_cases(ClaimVerdict.WRONG_ENTITY))
    def test_wrong_entity_detected(self, scenario) -> None:
        report = self.verifier.verify(
            agent_response=scenario.agent_response,
            tool_records=scenario.tool_records,
        )
        assert report.violations_count >= 1
        verdicts = [r.verdict for r in report.results]
        assert ClaimVerdict.WRONG_ENTITY in verdicts

    @pytest.mark.parametrize("scenario", get_planted_cases(ClaimVerdict.PARTIAL_SUCCESS))
    def test_partial_success_detected(self, scenario) -> None:
        report = self.verifier.verify(
            agent_response=scenario.agent_response,
            tool_records=scenario.tool_records,
        )
        assert report.violations_count >= 1
        verdicts = [r.verdict for r in report.results]
        assert ClaimVerdict.PARTIAL_SUCCESS in verdicts

    @pytest.mark.parametrize("scenario", get_planted_cases(ClaimVerdict.STATUS_MISMATCH))
    def test_status_mismatch_detected(self, scenario) -> None:
        report = self.verifier.verify(
            agent_response=scenario.agent_response,
            tool_records=scenario.tool_records,
        )
        assert report.violations_count >= 1
        verdicts = [r.verdict for r in report.results]
        assert ClaimVerdict.STATUS_MISMATCH in verdicts

    @pytest.mark.parametrize("scenario", get_planted_cases(ClaimVerdict.VERIFIED))
    def test_truthful_verified(self, scenario) -> None:
        report = self.verifier.verify(
            agent_response=scenario.agent_response,
            tool_records=scenario.tool_records,
        )
        assert report.violations_count == 0
        assert report.verified_count >= 1
        assert report.accuracy_percent == 100.0


class TestClaimVerifierEdgeCases:
    """Additional edge cases for robustness."""

    def setup_method(self) -> None:
        self.verifier = ClaimVerifier()

    def test_empty_response(self) -> None:
        report = self.verifier.verify("")
        assert report.total_claims == 0
        assert report.accuracy_percent == 100.0

    def test_unverifiable_claim(self) -> None:
        report = self.verifier.verify(
            agent_response="Your refund of ₹500 for order ORD-9999 has been issued.",
            tool_records=[],  # No tool execution records
        )
        assert report.total_claims == 1
        assert report.results[0].verdict == ClaimVerdict.UNVERIFIABLE

    def test_build_snapshots_from_tools(self) -> None:
        tool_records = [
            {
                "tool_name": "issue_refund",
                "tool_args": {"order_id": "ORD-101", "amount": 250},
                "tool_result": {"status": "completed", "refund_id": "REF-101", "amount": 250},
                "is_success": True,
            }
        ]
        snaps = self.verifier.build_snapshots_from_tools(tool_records)
        assert len(snaps) == 1
        assert snaps[0].entity_id == "ORD-101"
        assert snaps[0].actual_amount == 250.0
        assert snaps[0].tool_status == "success"
