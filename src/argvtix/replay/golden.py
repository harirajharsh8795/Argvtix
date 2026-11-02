"""
Golden Cases Dataset Loader.

Loads the ground-truth benchmark suite from config/golden_cases.yaml.
Provides strongly-typed GoldenCase objects for replay and regression testing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_GOLDEN_PATH = Path(__file__).resolve().parents[3] / "config" / "golden_cases.yaml"


class GoldenCase(BaseModel):
    """A single ground-truth benchmark evaluation case."""

    id: str = Field(..., description="Unique case identifier, e.g. gold_ref_001")
    workflow: str = Field(..., description="Workflow category (refund, cancel, balance, etc.)")
    ticket_text: str = Field(..., description="Customer input text in Hinglish or English")
    customer_id: str = Field(..., description="Customer profile ID")
    order_id: str | None = Field(default=None, description="Referenced order ID if applicable")
    product_id: str | None = Field(default=None, description="Referenced product ID if applicable")
    amount: float | None = Field(default=None, description="Monetary transaction amount")
    expected_intent: str = Field(..., description="Expected classified intent")
    expected_guard_decision: str = Field(
        ..., description="Expected decision: allow, block, ask_human"
    )
    expected_tool: str | None = Field(default=None, description="Expected MCP tool to execute")
    description: str = Field(default="", description="Rationale behind this expected outcome")


def load_golden_cases(path: str | Path | None = None) -> list[GoldenCase]:
    """
    Load all golden cases from the YAML configuration file.
    """
    target_path = Path(path) if path else DEFAULT_GOLDEN_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Golden cases file not found at: {target_path}")

    with open(target_path, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)

    raw_cases = data.get("cases", [])
    return [GoldenCase.model_validate(c) for c in raw_cases]


def get_golden_case(case_id: str, path: str | Path | None = None) -> GoldenCase | None:
    """Fetch a single golden case by its ID."""
    cases = load_golden_cases(path)
    for c in cases:
        if c.id == case_id:
            return c
    return None


def filter_golden_cases(
    workflow: str | None = None,
    expected_decision: str | None = None,
    path: str | Path | None = None,
) -> list[GoldenCase]:
    """Filter golden cases by workflow or expected guard decision."""
    cases = load_golden_cases(path)
    filtered = cases
    if workflow:
        filtered = [c for c in filtered if c.workflow == workflow]
    if expected_decision:
        dec = expected_decision.lower()
        filtered = [c for c in filtered if c.expected_guard_decision.lower() == dec]
    return filtered
