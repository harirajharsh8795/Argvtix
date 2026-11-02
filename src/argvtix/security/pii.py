"""
PII Detection and Masking Engine
Enterprise AI Reliability Platform (ARGVTIX)

Domain-agnostic PII Sanitizer:
- Built-in support for Indian PII: Aadhaar, Indian Mobile (+91/0), PAN card.
- Universal PII: Email addresses, Credit/Debit card numbers.
- Extensible entity rules for domain-specific identifiers (Patient ABHA/MRN, Bank IFSC, UPI IDs).
- Used by Gateway, Agent input pipelines, and Trace Store to ensure zero plain-text PII persistence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PIIEntity:
    """Details of a detected PII entity."""

    entity_type: str
    start: int
    end: int
    matched_text: str
    replacement: str


@dataclass
class MaskResult:
    """Result of a PII sanitization operation."""

    original_text: str
    masked_text: str
    entities: list[PIIEntity] = field(default_factory=list)
    has_pii: bool = False

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def types_detected(self) -> list[str]:
        return sorted(list({e.entity_type for e in self.entities}))


class PIIMasker:
    """
    High-performance Regex-based PII Sanitizer.
    Can be configured with domain-specific patterns.
    """

    DEFAULT_PATTERNS: dict[str, tuple[str, str]] = {
        # Indian Aadhaar: 12 digits, optionally grouped by 4
        "aadhaar": (
            r"\b[2-9]\d{3}[-\s]?\d{4}[-\s]?\d{4}\b",
            "[AADHAAR_MASKED]",
        ),
        # Indian PAN card: 5 uppercase letters, 4 digits, 1 uppercase letter
        "pan": (
            r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
            "[PAN_MASKED]",
        ),
        # Credit / Debit card: 16 digits, optionally grouped by 4
        "credit_card": (
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9]{2})[0-9]{12}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11})\b"
            r"|\b(?:\d{4}[-\s]){3}\d{4}\b",
            "[CARD_MASKED]",
        ),
        # Email address
        "email": (
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            "[EMAIL_MASKED]",
        ),
        # Indian Mobile Phone: 10 digits starting with 6, 7, 8, or 9; optional +91 or 0 prefix
        "phone": (
            r"(?:\+91[\-\s]?|0)?[6-9]\d{9}\b",
            "[PHONE_MASKED]",
        ),
        # UPI ID (Virtual Payment Address)
        "upi_id": (
            r"\b[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}\b",
            "[UPI_MASKED]",
        ),
    }

    def __init__(self, custom_patterns: dict[str, tuple[str, str]] | None = None) -> None:
        self.patterns = dict(self.DEFAULT_PATTERNS)
        if custom_patterns:
            self.patterns.update(custom_patterns)

        # Pre-compile regular expressions
        self._compiled: list[tuple[str, re.Pattern, str]] = [
            (name, re.compile(pat, re.IGNORECASE if name in ("email", "upi_id") else 0), repl)
            for name, (pat, repl) in self.patterns.items()
        ]

    def add_pattern(self, name: str, pattern: str, replacement: str) -> None:
        """Register a domain-specific entity pattern (e.g. MRN for clinics, Account for Fintech)."""
        self.patterns[name] = (pattern, replacement)
        self._compiled.append((name, re.compile(pattern), replacement))

    def detect_entities(self, text: str) -> list[PIIEntity]:
        """Detect all PII entities in the text without modifying it."""
        if not text:
            return []

        entities: list[PIIEntity] = []
        for name, regex, repl in self._compiled:
            for match in regex.finditer(text):
                matched_val = match.group(0)
                # Avoid overlapping with email when detecting upi
                if name == "upi_id" and "." in matched_val.split("@")[-1]:
                    continue
                entities.append(
                    PIIEntity(
                        entity_type=name,
                        start=match.start(),
                        end=match.end(),
                        matched_text=matched_val,
                        replacement=repl,
                    )
                )

        # Sort entities by start position
        entities.sort(key=lambda e: e.start)
        return entities

    def mask(self, text: str) -> MaskResult:
        """
        Scan input text and replace all detected PII occurrences with masking tokens.
        Preserves non-PII conversational text and context.
        """
        if not text:
            return MaskResult(original_text="", masked_text="", entities=[], has_pii=False)

        detected = self.detect_entities(text)
        if not detected:
            return MaskResult(original_text=text, masked_text=text, entities=[], has_pii=False)

        # Non-overlapping replacement from left to right
        result_chars: list[str] = []
        curr_idx = 0

        # Filter overlapping intervals: pick the earlier or longer one
        non_overlapping: list[PIIEntity] = []
        for ent in detected:
            if not non_overlapping:
                non_overlapping.append(ent)
            else:
                last = non_overlapping[-1]
                if ent.start >= last.end:
                    non_overlapping.append(ent)
                elif (ent.end - ent.start) > (last.end - last.start):
                    # Replace with longer match
                    non_overlapping[-1] = ent

        for ent in non_overlapping:
            if ent.start > curr_idx:
                result_chars.append(text[curr_idx : ent.start])
            result_chars.append(ent.replacement)
            curr_idx = ent.end

        if curr_idx < len(text):
            result_chars.append(text[curr_idx:])

        masked_str = "".join(result_chars)
        return MaskResult(
            original_text=text,
            masked_text=masked_str,
            entities=non_overlapping,
            has_pii=True,
        )

    def contains_pii(self, text: str) -> bool:
        """Quick check if text has any sensitive PII."""
        return len(self.detect_entities(text)) > 0
