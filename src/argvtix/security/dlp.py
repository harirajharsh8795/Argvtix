"""
Data Loss Prevention (DLP) & Outbound Security Filter
Enterprise AI Reliability Platform (ARGVTIX)

Prevents:
1. PII leakage in outgoing responses.
2. System prompt and internal instruction leakage.
3. Raw error tracebacks and database connection string leaks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from argvtix.security.pii import PIIMasker


@dataclass
class DLPViolation:
    """Details of a detected DLP violation."""
    rule_name: str
    severity: str  # 'low' | 'medium' | 'high' | 'critical'
    description: str
    snippet: str


@dataclass
class DLPCheckResult:
    """Result of an outbound response DLP audit."""
    is_safe: bool
    violations: list[DLPViolation] = field(default_factory=list)
    sanitized_text: str = ""

    @property
    def has_critical(self) -> bool:
        return any(v.severity == "critical" for v in self.violations)


class DLPFilter:
    """
    Outbound response firewall for AI agents.
    Inspects responses before they reach the user/customer.
    """

    SYSTEM_LEAK_PATTERNS = [
        (
            "system_prompt_leak",
            "critical",
            r"(?i)\b(you are an ai assistant|internal prompt|system instructions|do not reveal this to the user|developer guidelines)\b",
            "Internal system prompt instructions leaked in response",
        ),
        (
            "credential_leak",
            "critical",
            r"(?i)\b(bearer\s+[a-zA-Z0-9_\-\.]{20,}|postgres://[^\s]+|mongodb://[^\s]+|api[_\-]?key\s*[:=]\s*['\"][a-zA-Z0-9_\-]+['\"])\b",
            "Credential, connection string, or secret token detected in output",
        ),
        (
            "stacktrace_leak",
            "high",
            r"(?i)(Traceback \(most recent call last\)|sqlalchemy\.exc\.|psycopg2\.|ZeroDivisionError|NullPointerException)",
            "Raw application exception or database error trace leaked",
        ),
    ]

    def __init__(self, pii_masker: PIIMasker | None = None) -> None:
        self.pii_masker = pii_masker or PIIMasker()
        self._compiled_leaks = [
            (name, sev, re.compile(pat), desc)
            for name, sev, pat, desc in self.SYSTEM_LEAK_PATTERNS
        ]

    def inspect(self, response_text: str) -> DLPCheckResult:
        """
        Audit an outbound response for security and privacy violations.
        """
        if not response_text:
            return DLPCheckResult(is_safe=True, violations=[], sanitized_text="")

        violations: list[DLPViolation] = []

        # 1. Check for PII in output
        pii_entities = self.pii_masker.detect_entities(response_text)
        for ent in pii_entities:
            violations.append(
                DLPViolation(
                    rule_name=f"pii_{ent.entity_type}",
                    severity="high",
                    description=f"Outbound response contains unmasked {ent.entity_type}",
                    snippet=ent.matched_text,
                )
            )

        # 2. Check for system/credential/traceback leaks
        for name, sev, regex, desc in self._compiled_leaks:
            match = regex.search(response_text)
            if match:
                violations.append(
                    DLPViolation(
                        rule_name=name,
                        severity=sev,
                        description=desc,
                        snippet=match.group(0)[:60],
                    )
                )

        # 3. Generate sanitized text (mask PII and redact critical leaks)
        sanitized = self.pii_masker.mask(response_text).masked_text
        for _name, _sev, regex, _desc in self._compiled_leaks:
            sanitized = regex.sub("[REDACTED_SYSTEM_CONTENT]", sanitized)

        is_safe = len(violations) == 0

        return DLPCheckResult(
            is_safe=is_safe,
            violations=violations,
            sanitized_text=sanitized,
        )

    def sanitize(self, response_text: str) -> str:
        """Convenience method returning safe sanitized text."""
        return self.inspect(response_text).sanitized_text
