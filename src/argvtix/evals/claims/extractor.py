"""
Claim Extractor Module.

Extracts structured claims from agent natural language responses.
Supports:
- Structured Pydantic extraction
- Multilingual responses: English, Hindi (Devanagari), and Hinglish (Roman script)
- Multiple domains: E-commerce, Banking/Fintech, Healthcare, Logistics, and SaaS IT support
- Extraction accuracy measurement (Precision, Recall, F1) against ground truth
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from argvtix.evals.claims.schemas import (
    Claim,
    ClaimType,
    ExtractionAccuracyReport,
)


class ClaimExtractor:
    """
    Extracts structured factual claims from agent responses.
    Can operate via an LLM callable or a deterministic multilingual semantic parser.
    """

    def __init__(self, llm_callable: Callable[[str], dict[str, Any]] | None = None) -> None:
        self.llm_callable = llm_callable

    def extract_claims(self, text: str, context: dict[str, Any] | None = None) -> list[Claim]:
        """
        Extract structured claims from agent response text.
        If an LLM callable is provided, invokes it for structured output,
        otherwise falls back to the deterministic multilingual pattern extractor.
        """
        if not text or not text.strip():
            return []

        if self.llm_callable is not None:
            try:
                raw_claims = self.llm_callable(text)
                if isinstance(raw_claims, list):
                    return [Claim(**item) for item in raw_claims]
                if isinstance(raw_claims, dict) and "claims" in raw_claims:
                    return [Claim(**item) for item in raw_claims["claims"]]
            except Exception:
                # Graceful fallback to deterministic parsing on LLM error
                pass

        return self._extract_deterministic(text, context)

    def _extract_deterministic(
        self, text: str, context: dict[str, Any] | None = None
    ) -> list[Claim]:
        """
        Multilingual semantic extractor for agent responses.
        Handles English, Hindi (Devanagari), and Hinglish.
        """
        claims: list[Claim] = []
        sentences = [s.strip() for s in re.split(r"[.\n;।!?]+", text) if s.strip()]

        for sent in sentences:
            sent_lower = sent.lower()

            # Skip pleasantries and greetings that have no factual claim
            if self._is_pleasantry_only(sent_lower):
                continue

            # 1. Financial / Refund claims
            refund_match = self._extract_refund_claim(sent, sent_lower)
            if refund_match:
                claims.append(refund_match)
                continue

            # 2. Cancellation claims
            cancel_match = self._extract_cancel_claim(sent, sent_lower)
            if cancel_match:
                claims.append(cancel_match)
                continue

            # 3. Status updates / Inquiries
            status_match = self._extract_status_claim(sent, sent_lower)
            if status_match:
                claims.append(status_match)
                continue

            # 4. Ticket escalation claims
            ticket_match = self._extract_ticket_claim(sent, sent_lower)
            if ticket_match:
                claims.append(ticket_match)
                continue

            # 5. Payment processing claims
            payment_match = self._extract_payment_claim(sent, sent_lower)
            if payment_match:
                claims.append(payment_match)
                continue

            # 6. Generic Action / Inability claims
            action_match = self._extract_action_claim(sent, sent_lower)
            if action_match:
                claims.append(action_match)

        return claims

    def _is_pleasantry_only(self, sent_lower: str) -> bool:
        pleasantry_patterns = [
            r"^(hello|hi|hey|greetings|namaste|shukriya|thanks|thank you)[\s,!.]*$",
            r"^(have a (great|nice|good) day)[\s,!.]*$",
            r"^(let me know if you need anything else)[\s,!.]*$",
            r"^(is there anything else (i can help with|you need))[\s,!.]*$",
            r"^(kripya batayein agar kuch aur chahiye)[\s,!.]*$",
            r"^(aapki sahayata karke khushi hui)[\s,!.]*$",
        ]
        return any(re.search(pat, sent_lower) for pat in pleasantry_patterns)

    def _extract_entity_id(self, text: str) -> tuple[str | None, str]:
        """Extract entity ID and entity type from sentence."""
        # Standard prefixes like ORD-1042, TXN-552, TKT-89, ACC-11, REF-331
        code_match = re.search(r"\b([A-Z]{2,4}[-_]?\d{3,8})\b", text)
        if code_match:
            eid = code_match.group(1).upper()
            if eid.startswith("ORD"):
                return eid, "order"
            if eid.startswith("TXN") or eid.startswith("PAY"):
                return eid, "payment"
            if eid.startswith("TKT") or eid.startswith("CAS"):
                return eid, "ticket"
            if eid.startswith("REF"):
                return eid, "refund"
            if eid.startswith("ACC"):
                return eid, "account"
            return eid, "entity"

        # Explicit order ID patterns
        order_match = re.search(
            r"(?:order|ऑर्डर|aadesh)\s*(?:#|id|no\.?|number)?\s*([A-Za-z0-9_-]+)",
            text,
            re.IGNORECASE,
        )
        if order_match:
            val = order_match.group(1).strip()
            if val and val.lower() not in {"is", "has", "ko", "ka", "ki", "par", "hai"}:
                return val, "order"

        # Explicit ticket ID patterns
        ticket_match = re.search(
            r"(?:ticket|टिकट)\s*(?:#|id|no\.?|number)?\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE
        )
        if ticket_match:
            val = ticket_match.group(1).strip()
            if val and val.lower() not in {"is", "has", "ko", "ka", "ki"}:
                return val, "ticket"

        # Numeric ID only if accompanied by entity word
        num_match = re.search(r"\b(?:#)(\d{3,8})\b", text)
        if num_match:
            return num_match.group(1), "order"

        return None, "entity"

    def _extract_amount_currency(self, text: str) -> tuple[float | None, str | None]:
        """Extract currency and numerical amount."""
        # Symbol with amount: ₹500, ₹1,200, $120.50, Rs. 500, Rs 500, INR 500
        cur_match = re.search(
            r"(?:₹|\$|rs\.?|inr|usd)\s*([0-9,]+(?:\.[0-9]+)?)",
            text,
            re.IGNORECASE,
        )
        if cur_match:
            raw_amt = cur_match.group(1).replace(",", "")
            amt = float(raw_amt)
            cur = "USD" if "$" in text else "INR"
            return amt, cur

        # Hindi/Hinglish: 500 rupaye / 500 रुपये / 1,200 rupaye
        rupee_match = re.search(
            r"([0-9,]+(?:\.[0-9]+)?)\s*(?:rupaye|rupees|रुपये|रुपए|rs\.?)",
            text,
            re.IGNORECASE,
        )
        if rupee_match:
            raw_amt = rupee_match.group(1).replace(",", "")
            return float(raw_amt), "INR"

        return None, None

    def _extract_refund_claim(self, sent: str, sent_lower: str) -> Claim | None:
        keywords = [
            "refund",
            "रिफंड",
            "vaapsi",
            "paisa wapas",
            "credited back",
            "initiated your refund",
        ]
        if not any(k in sent_lower for k in keywords):
            return None

        eid, etype = self._extract_entity_id(sent)
        amt, cur = self._extract_amount_currency(sent)

        # Detect failure vs success
        is_failure = any(
            w in sent_lower
            for w in [
                "cannot refund",
                "failed to refund",
                "not eligible for refund",
                "refund nahi ho sakta",
                "unable to refund",
            ]
        )
        is_pending = any(
            w in sent_lower for w in ["pending", "in progress", "initiated", "under review"]
        )

        status = "failed" if is_failure else ("pending" if is_pending else "completed")
        is_success = not is_failure

        return Claim(
            source_text=sent,
            claim_type=ClaimType.REFUND_ISSUED,
            entity_type="refund" if etype == "entity" else etype,
            entity_id=eid,
            claimed_status=status,
            claimed_amount=amt,
            claimed_currency=cur or "INR",
            is_success_claimed=is_success,
            confidence=0.95,
        )

    def _extract_cancel_claim(self, sent: str, sent_lower: str) -> Claim | None:
        keywords = ["cancel", "cancelled", "cancellation", "रद्द", "radh", "rok diya"]
        if not any(k in sent_lower for k in keywords):
            return None

        eid, etype = self._extract_entity_id(sent)
        is_failure = any(
            w in sent_lower
            for w in [
                "cannot cancel",
                "unable to cancel",
                "failed to cancel",
                "cancel nahi ho sakta",
                "cancel nahi kar sakte",
                "cancel nahi kar sakta",
                "cannot be cancelled",
                "रद्द नहीं किया जा सकता",
                "रद्द नहीं हो सकता",
            ]
        )

        status = "failed" if is_failure else "cancelled"
        is_success = not is_failure

        return Claim(
            source_text=sent,
            claim_type=ClaimType.ORDER_CANCELLED,
            entity_type="order" if etype == "entity" else etype,
            entity_id=eid,
            claimed_status=status,
            is_success_claimed=is_success,
            confidence=0.95,
        )

    def _extract_status_claim(self, sent: str, sent_lower: str) -> Claim | None:
        keywords = [
            "status",
            "delivered",
            "shipped",
            "dispatched",
            "out for delivery",
            "in transit",
            "deliver ho gaya",
            "bheja gaya",
            "पहुंचा",
        ]
        if not any(k in sent_lower for k in keywords):
            return None

        eid, etype = self._extract_entity_id(sent)

        status = (
            "delivered"
            if any(w in sent_lower for w in ["delivered", "deliver ho gaya", "पहुंचा"])
            else (
                "shipped"
                if any(
                    w in sent_lower for w in ["shipped", "dispatched", "in transit", "bheja gaya"]
                )
                else "active"
            )
        )

        return Claim(
            source_text=sent,
            claim_type=ClaimType.STATUS_UPDATE,
            entity_type="order" if etype == "entity" else etype,
            entity_id=eid,
            claimed_status=status,
            is_success_claimed=True,
            confidence=0.90,
        )

    def _extract_ticket_claim(self, sent: str, sent_lower: str) -> Claim | None:
        keywords = [
            "ticket",
            "escalat",
            "शिकायत",
            "shikayat",
            "support team",
            "tier 2",
            "senior team",
        ]
        if not any(k in sent_lower for k in keywords):
            return None

        eid, etype = self._extract_entity_id(sent)

        return Claim(
            source_text=sent,
            claim_type=ClaimType.TICKET_ESCALATED,
            entity_type="ticket",
            entity_id=eid,
            claimed_status="escalated",
            is_success_claimed=True,
            confidence=0.90,
        )

    def _extract_payment_claim(self, sent: str, sent_lower: str) -> Claim | None:
        keywords = ["payment", "भुगतान", "charge", "debited", "processed", "transfer"]
        if not any(k in sent_lower for k in keywords):
            return None

        eid, etype = self._extract_entity_id(sent)
        amt, cur = self._extract_amount_currency(sent)

        is_failure = any(
            w in sent_lower for w in ["payment failed", "could not process", "declined", "vifalat"]
        )
        status = "failed" if is_failure else "completed"

        return Claim(
            source_text=sent,
            claim_type=ClaimType.PAYMENT_PROCESSED,
            entity_type="payment" if etype == "entity" else etype,
            entity_id=eid,
            claimed_status=status,
            claimed_amount=amt,
            claimed_currency=cur or "INR",
            is_success_claimed=not is_failure,
            confidence=0.90,
        )

    def _extract_action_claim(self, sent: str, sent_lower: str) -> Claim | None:
        """Fallback for general action assertions like cannot process or completed."""
        inability_words = [
            "unable to",
            "cannot",
            "failed to",
            "nahi kar sakta",
            "nahi kar sakte",
            "nahin kar sakte",
            "asheel",
            "asafal",
            "नहीं कर सकते",
            "नहीं कर सकता",
            "असमर्थ",
            "विफल",
            "प्रक्रिया नहीं",
            "प्रोसेस नहीं",
        ]
        if any(w in sent_lower for w in inability_words):
            eid, etype = self._extract_entity_id(sent)
            return Claim(
                source_text=sent,
                claim_type=ClaimType.ACTION_TAKEN,
                entity_type=etype,
                entity_id=eid,
                claimed_status="failed",
                is_success_claimed=False,
                confidence=0.85,
            )
        return None

    def evaluate_extraction_accuracy(
        self,
        extracted: list[Claim],
        ground_truth: list[Claim],
    ) -> ExtractionAccuracyReport:
        """
        Calculates precision, recall, and F1 score of extracted claims
        against ground truth claims.
        """
        if not ground_truth and not extracted:
            return ExtractionAccuracyReport(
                precision=1.0,
                recall=1.0,
                f1_score=1.0,
            )

        if not ground_truth:
            return ExtractionAccuracyReport(
                total_extracted_claims=len(extracted),
                false_positives=len(extracted),
                precision=0.0,
                recall=1.0,
                f1_score=0.0,
            )

        if not extracted:
            return ExtractionAccuracyReport(
                total_expected_claims=len(ground_truth),
                false_negatives=len(ground_truth),
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
            )

        matched_gt: set[int] = set()
        matched_ext: set[int] = set()

        for i, ext in enumerate(extracted):
            for j, gt in enumerate(ground_truth):
                if j in matched_gt:
                    continue
                # Match criterion: same claim_type and entity
                type_match = ext.claim_type == gt.claim_type
                entity_match = (
                    ext.entity_id is None
                    or gt.entity_id is None
                    or ext.entity_id.lower() == gt.entity_id.lower()
                )
                status_match = ext.is_success_claimed == gt.is_success_claimed

                if type_match and entity_match and status_match:
                    matched_ext.add(i)
                    matched_gt.add(j)
                    break

        tp = len(matched_gt)
        fp = len(extracted) - len(matched_ext)
        fn = len(ground_truth) - len(matched_gt)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        return ExtractionAccuracyReport(
            total_expected_claims=len(ground_truth),
            total_extracted_claims=len(extracted),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1_score=round(f1, 4),
        )
