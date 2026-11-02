"""
Evaluation Metrics Module.

Computes core reliability, safety, and performance metrics for AI agent runs:
1. Intent Classification Accuracy
2. Action Guard Alignment Rate
3. Tool Calling Accuracy
4. Language-wise Performance (English, Hindi, Hinglish)
5. Latency Percentiles (p50, p90, p95)
6. Cost per 100 requests
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LanguageMetrics:
    """Breakdown of accuracy across language variants."""

    total: int = 0
    passed: int = 0
    accuracy_percent: float = 0.0


@dataclass
class EvaluationSummary:
    """Consolidated evaluation summary for a model/prompt run."""

    total_evals: int
    overall_accuracy: float
    intent_accuracy: float
    guard_alignment: float
    tool_accuracy: float
    p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    total_cost_usd: float
    cost_per_100_usd: float
    language_breakdown: dict[str, LanguageMetrics] = field(default_factory=dict)
    workflow_breakdown: dict[str, float] = field(default_factory=dict)


def detect_language(text: str) -> str:
    """
    Heuristic language detector:
    - If Devanagari script present -> 'hi' (Hindi)
    - If English with Hindi transliterated keywords -> 'hinglish'
    - Otherwise -> 'en' (English)
    """
    # Check for Devanagari Unicode block (U+0900 to U+097F)
    if any("\u0900" <= char <= "\u097f" for char in text):
        return "hi"

    hinglish_keywords = {
        "karo",
        "chahiye",
        "mera",
        "meri",
        "tha",
        "thi",
        "hai",
        "nahi",
        "aaya",
        "ka",
        "ki",
        "ke",
        "ko",
        "se",
        "pe",
        "kya",
        "bhejo",
        "batao",
        "karna",
        "paas",
        "kab",
        "kitna",
        "dobara",
        "galti",
        "paisa",
        "khata",
        "sambhal",
    }
    words = set(text.lower().split())
    if len(words & hinglish_keywords) >= 1:
        return "hinglish"

    return "en"


def compute_percentiles(latencies: list[float]) -> tuple[float, float, float]:
    """Calculate p50, p90, and p95 latencies in ms."""
    if not latencies:
        return 0.0, 0.0, 0.0
    sorted_l = sorted(latencies)
    n = len(sorted_l)

    def _percentile(p: float) -> float:
        k = (n - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, n - 1)
        d = k - f
        return sorted_l[f] + (sorted_l[c] - sorted_l[f]) * d

    p50 = _percentile(50.0)
    p90 = _percentile(90.0)
    p95 = _percentile(95.0)
    return round(p50, 1), round(p90, 1), round(p95, 1)


def compute_evaluation_summary(eval_items: list[dict[str, Any]]) -> EvaluationSummary:
    """
    Given a list of evaluation case results:
    [
      {
        "workflow": "refund",
        "ticket_text": "...",
        "expected_intent": "refund",
        "actual_intent": "refund",
        "expected_guard": "allow",
        "actual_guard": "allow",
        "expected_tool": "issue_refund",
        "actual_tool": "issue_refund",
        "latency_ms": 45.0,
        "cost_usd": 0.0002,
      },
      ...
    ]
    Computes a comprehensive EvaluationSummary.
    """
    if not eval_items:
        return EvaluationSummary(
            total_evals=0,
            overall_accuracy=0.0,
            intent_accuracy=0.0,
            guard_alignment=0.0,
            tool_accuracy=0.0,
            p50_latency_ms=0.0,
            p90_latency_ms=0.0,
            p95_latency_ms=0.0,
            total_cost_usd=0.0,
            cost_per_100_usd=0.0,
        )

    total = len(eval_items)
    intent_correct = 0
    guard_correct = 0
    tool_correct = 0
    passed_total = 0

    latencies: list[float] = []
    total_cost = 0.0

    lang_data: dict[str, dict[str, int]] = {
        "en": {"total": 0, "passed": 0},
        "hi": {"total": 0, "passed": 0},
        "hinglish": {"total": 0, "passed": 0},
    }

    wf_data: dict[str, dict[str, int]] = {}

    for item in eval_items:
        ticket = item.get("ticket_text", "")
        lang = detect_language(ticket)
        lang_data[lang]["total"] += 1

        wf = item.get("workflow", "general")
        if wf not in wf_data:
            wf_data[wf] = {"total": 0, "passed": 0}
        wf_data[wf]["total"] += 1

        # Check intent
        exp_intent = str(item.get("expected_intent", "")).lower()
        act_intent = str(item.get("actual_intent", "")).lower()
        i_match = exp_intent == act_intent
        if i_match:
            intent_correct += 1

        # Check guard
        exp_guard = str(item.get("expected_guard", "")).lower()
        act_guard = str(item.get("actual_guard", "")).lower()
        g_match = exp_guard == act_guard
        if g_match:
            guard_correct += 1

        # Check tool
        exp_tool = item.get("expected_tool")
        act_tool = item.get("actual_tool")
        t_match = (exp_tool is None and act_tool is None) or (
            exp_tool is not None
            and act_tool is not None
            and str(exp_tool).lower() == str(act_tool).lower()
        )
        if t_match:
            tool_correct += 1

        # Case passes if intent AND guard match
        is_case_pass = i_match and g_match
        if is_case_pass:
            passed_total += 1
            lang_data[lang]["passed"] += 1
            wf_data[wf]["passed"] += 1

        lat = float(item.get("latency_ms", 0.0))
        latencies.append(lat)
        total_cost += float(item.get("cost_usd", 0.0))

    p50, p90, p95 = compute_percentiles(latencies)

    # Format language breakdown
    lang_breakdown: dict[str, LanguageMetrics] = {}
    for l_key, counts in lang_data.items():
        if counts["total"] > 0:
            acc = round((counts["passed"] / counts["total"]) * 100.0, 1)
            lang_breakdown[l_key] = LanguageMetrics(
                total=counts["total"],
                passed=counts["passed"],
                accuracy_percent=acc,
            )

    # Format workflow breakdown
    wf_breakdown: dict[str, float] = {}
    for w_key, counts in wf_data.items():
        if counts["total"] > 0:
            wf_breakdown[w_key] = round((counts["passed"] / counts["total"]) * 100.0, 1)

    cost_per_100 = (total_cost / total) * 100.0 if total > 0 else 0.0

    return EvaluationSummary(
        total_evals=total,
        overall_accuracy=round((passed_total / total) * 100.0, 1),
        intent_accuracy=round((intent_correct / total) * 100.0, 1),
        guard_alignment=round((guard_correct / total) * 100.0, 1),
        tool_accuracy=round((tool_correct / total) * 100.0, 1),
        p50_latency_ms=p50,
        p90_latency_ms=p90,
        p95_latency_ms=p95,
        total_cost_usd=round(total_cost, 5),
        cost_per_100_usd=round(cost_per_100, 4),
        language_breakdown=lang_breakdown,
        workflow_breakdown=wf_breakdown,
    )
