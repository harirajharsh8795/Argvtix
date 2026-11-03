"""
Labelled Claim Extraction Benchmark Dataset Loader.

Loads the human-annotated ground-truth claim extraction dataset from config/claim_extraction_gold_set.yaml.
Used to evaluate and measure precision, recall, and F1 score of claim extraction models independently
from planted verification scenarios.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from argvtix.evals.claims.schemas import Claim

CONFIG_DIR = Path(__file__).resolve().parents[4] / "config"
DEFAULT_LABELLED_PATH = CONFIG_DIR / "claim_extraction_gold_set.yaml"


class LabelledClaimCase(BaseModel):
    """A human-annotated reference text with ground-truth claims."""

    id: str
    domain: str
    language: str
    text: str
    expected_claims: list[Claim] = Field(default_factory=list)


def load_labelled_claims(path: str | Path | None = None) -> list[LabelledClaimCase]:
    """Loads reference labelled cases from YAML."""
    resolved_path = Path(path) if path else DEFAULT_LABELLED_PATH
    if not resolved_path.exists():
        return []

    with open(resolved_path, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    raw_cases = data.get("cases", [])
    cases: list[LabelledClaimCase] = []
    for c in raw_cases:
        cases.append(LabelledClaimCase.model_validate(c))

    return cases
