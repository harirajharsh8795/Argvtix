"""
Claim-vs-State Verification Module.

Enables deterministic verification of claims made in AI agent responses against
the ground truth execution state (tool results, database rows written, and entity states).
Detects 6 critical hallucination & discrepancy categories:
1. False Success (tool failed/no write, agent claimed success)
2. False Failure (tool succeeded, agent claimed failure)
3. Omitted Failure (tool failed, agent omitted failure mention)
4. Wrong Entity (agent acted on or claimed entity X, tool touched entity Y)
5. Partial Success (agent claimed full amount/action, tool executed partial)
6. Status Mismatch (agent claimed status A, DB/tool reflects status B)
"""

from earp.evals.claims.extractor import ClaimExtractor
from earp.evals.claims.planted_cases import PlantedScenario, get_planted_cases
from earp.evals.claims.schemas import (
    Claim,
    ClaimsEvaluationReport,
    ClaimSeverity,
    ClaimType,
    ClaimVerdict,
    ClaimVerificationResult,
    EntityStateSnapshot,
    EvidenceBundle,
    ExtractionAccuracyReport,
)
from earp.evals.claims.verifier import ClaimVerifier

__all__ = [
    "Claim",
    "ClaimExtractor",
    "ClaimSeverity",
    "ClaimType",
    "ClaimVerdict",
    "ClaimVerificationResult",
    "ClaimVerifier",
    "ClaimsEvaluationReport",
    "EntityStateSnapshot",
    "EvidenceBundle",
    "ExtractionAccuracyReport",
    "PlantedScenario",
    "get_planted_cases",
]
