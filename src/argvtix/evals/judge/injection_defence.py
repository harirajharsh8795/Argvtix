"""
LLM Judge Injection Defence (MISSING-01).

Protects automated evaluation judges from adversarial jailbreaks & scoring manipulation:
- Detects prompt injection attempts embedded inside customer tickets or agent responses
- Flags 'judge-injection-suspected' and aborts judge call to prevent metric poisoning
- Multilingual support (English, Hindi, Hinglish)
"""

from __future__ import annotations

import re
from collections.abc import Sequence


class JudgeInjectionDefence:
    """Pre-evaluation filter that guards LLM judges against adversarial hijacking."""

    INJECTION_PATTERNS: Sequence[str] = [
        # English patterns
        r"ignore\s+(?:all\s+)?previous\s+(?:instructions|rules|prompts)",
        r"disregard\s+(?:the\s+)?rubric",
        r"override\s+(?:the\s+)?(?:score|rating|evaluation)",
        r"(?:give|award|assign)\s+(?:me\s+)?(?:a\s+)?(?:10/10|5/5|perfect|maximum)\s*(?:score|rating)?",
        r"you\s+are\s+now\s+a\s+judge\s+that\s+always\s+(?:gives|rates)",
        r"rate\s+this\s+(?:response\s+)?(?:as\s+)?10(?:\.0)?",
        r"system\s*:\s*score\s*=\s*10",
        r"<\/?(?:evaluation|score|verdict|rubric)>",
        # Hinglish patterns
        r"purane\s+(?:niyam|instructions)\s+bhool\s+jao",
        r"(?:full|maximum)\s+(?:marks|score)\s+de\s+do",
        r"10\s+(?:out\s+of\s+10|mein\s+se\s+10)\s+do",
        r"rubric\s+ko\s+chhod\s+kar",
        # Hindi Devanagari patterns
        r"पुराने\s+(?:निर्देश|नियम)\s+भूल\s+जाओ",
        r"(?:10/10|पूरे)\s+अंक\s+दो",
        r"रुब्रिक\s+को\s+नजरअंदाज\s+करो",
    ]

    def __init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def scan_for_injection(self, text: str) -> tuple[bool, str | None]:
        """
        Inspects text for adversarial manipulation attempts targeting the judge.
        Returns (is_suspected, matched_pattern_reason).
        """
        if not text:
            return False, None

        for pattern in self._compiled:
            match = pattern.search(text)
            if match:
                return True, f"Adversarial judge injection pattern detected: '{match.group(0)}'"

        return False, None
