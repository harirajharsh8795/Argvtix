"""
Argvtix Failure Taxonomy.

Defines the 13 canonical failure modes for enterprise AI agents,
categorized into 4 critical reliability pillars:
1. Safety & Boundary Violations (PII leaks, Prompt Injection)
2. Policy & Authorization Violations (Refund cap, Customer mismatch, Window breach)
3. Ground-Truth & State Discrepancies (False success/failure, Omitted failure, Wrong entity, Partial success, Status desync)
4. Knowledge & Capability Failures (Hallucinated tool, Out-of-scope hallucination)
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    """High-level pillar classification."""

    SAFETY_SECURITY = "safety_security"
    POLICY_AUTHORIZATION = "policy_authorization"
    STATE_GROUNDING = "state_grounding"
    KNOWLEDGE_REASONING = "knowledge_reasoning"
    BENIGN = "benign"


class FailureTaxonomy(str, Enum):
    """The 13 fine-grained failure modes evaluated by Argvtix Bench."""

    # 1. Knowledge & Tool Calling
    HALLUCINATED_TOOL = "hallucinated_tool"
    UNANSWERABLE_HALLUCINATION = "unanswerable_hallucination"

    # 2. Policy & Authorization
    POLICY_VIOLATION_REFUND_LIMIT = "policy_violation_refund_limit"
    POLICY_VIOLATION_WINDOW = "policy_violation_window"
    UNAUTHORIZED_ACCESS_CUSTOMER_MISMATCH = "unauthorized_access_customer_mismatch"

    # 3. Safety & Security
    PROMPT_INJECTION_COMPLIANCE = "prompt_injection_compliance"
    PII_LEAK_IN_RESPONSE = "pii_leak_in_response"

    # 4. State Grounding & Claims (Claim-vs-State)
    FALSE_SUCCESS_CLAIM = "false_success_claim"
    FALSE_FAILURE_CLAIM = "false_failure_claim"
    OMITTED_FAILURE_CLAIM = "omitted_failure_claim"
    WRONG_ENTITY_REFERENCE = "wrong_entity_reference"
    PARTIAL_SUCCESS_MISMATCH = "partial_success_mismatch"
    STATUS_DESYNCHRONIZATION = "status_desynchronization"

    # 5. Clean Baseline
    BENIGN_PASS = "benign_pass"


class BenchmarkCase(BaseModel):
    """A labelled evaluation scenario in the Argvtix Bench dataset."""

    id: str = Field(..., description="Unique benchmark case ID (e.g. dev_001, held_001)")
    domain: str = Field(..., description="Domain: ecommerce, fintech, healthcare, logistics, saas")
    language: str = Field(..., description="Language: en, hi, hinglish")
    input_text: str = Field(..., description="Customer input text")
    customer_id: str = Field(..., description="Target customer ID")
    order_id: str | None = Field(default=None)
    amount: float | None = Field(default=None)
    expected_failure: FailureTaxonomy = Field(
        ..., description="Expected failure mode, or BENIGN_PASS"
    )
    expected_category: FailureCategory = Field(..., description="Pillar category")
    expected_guard_decision: str = Field(default="allow")  # allow, block, ask_human
    description: str = Field(default="")
    is_adversarial: bool = Field(default=False)
