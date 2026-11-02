"""
Policy Conflict Benchmark Dataset (60 Ground-Truth Pairs)
30 Injected Contradictory Pairs + 30 Consistent/Clean Pairs
Used to measure Precision, Recall, and F1 Score of the Policy Conflict Detector.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argvtix.watchdog.conflicts.detector import PolicyConflictDetector
from argvtix.watchdog.conflicts.schemas import ConflictVerdict


@dataclass
class ConflictBenchmarkCase:
    case_id: str
    topic: str
    clause_a_text: str
    clause_b_text: str
    expected_verdict: ConflictVerdict
    description: str


def build_conflict_benchmark_dataset() -> list[ConflictBenchmarkCase]:
    """Generate 60 standard ground-truth evaluation pairs (30 conflicts + 30 clean)."""
    cases: list[ConflictBenchmarkCase] = []

    # ------------------------------------------------------------------------
    # 30 CONFLICTING PAIRS (Injected Discrepancies)
    # ------------------------------------------------------------------------
    topics_and_variants = [
        # 1-10: Refund window conflicts
        ("refund_window", "Customers are eligible for a refund within 7 days of delivery.", "Refund window of 30 days is guaranteed for all orders.", "7 vs 30 days"),
        ("refund_window", "Items must be returned for refund within 14 days.", "Full refunds allowed for 45 days after purchase.", "14 vs 45 days"),
        ("refund_window", "Cash refund request accepted within 10 days.", "Refunds processed within 30 days unconditionally.", "10 vs 30 days"),
        ("refund_window", "Eligible within 5 days.", "Refund allowed for 15 days.", "5 vs 15 days"),
        ("refund_window", "Product return refund within 7 days.", "30 days money-back guarantee.", "7 vs 30 days"),
        ("refund_window", "Claims accepted within 3 days.", "Claims window of 14 days.", "3 vs 14 days"),
        ("refund_window", "Refund permitted within 21 days.", "Return window of 7 days.", "21 vs 7 days"),
        ("refund_window", "Allowed within 30 business days.", "Must request within 10 business days.", "30 vs 10 days"),
        ("refund_window", "Refund within 15 days.", "Refund window of 60 days.", "15 vs 60 days"),
        ("refund_window", "Request refund within 7 days.", "Return window of 28 days.", "7 vs 28 days"),

        # 11-20: Approval threshold conflicts
        ("refund_approval_threshold", "Supervisor approval required for amounts above Rs 10,000.", "Manager approval required for amounts exceeding Rs 25,000.", "10K vs 25K limit"),
        ("refund_approval_threshold", "Approval required above Rs 5,000.", "Supervisor approval for amounts over Rs 15,000.", "5K vs 15K limit"),
        ("refund_approval_threshold", "Auto-approve up to Rs 10,000.", "Manual approval required above Rs 20,000.", "10K vs 20K limit"),
        ("refund_approval_threshold", "Requires supervisor approval above Rs 10,000.", "Supervisor sign-off needed above Rs 50,000.", "10K vs 50K limit"),
        ("refund_approval_threshold", "Amounts over Rs 10,000 need approval.", "Escalate if above Rs 8,000.", "10K vs 8K limit"),
        ("refund_approval_threshold", "Manager approval for amounts over Rs 30,000.", "Supervisor approval above Rs 10,000.", "30K vs 10K limit"),
        ("refund_approval_threshold", "Approval needed exceeding Rs 10,000.", "Team lead sign-off over Rs 12,000.", "10K vs 12K limit"),
        ("refund_approval_threshold", "Approval required above Rs 10,000.", "Threshold is over Rs 18,000.", "10K vs 18K limit"),
        ("refund_approval_threshold", "Mandatory approval above Rs 10,000.", "Approval required exceeding Rs 2,500.", "10K vs 2.5K limit"),
        ("refund_approval_threshold", "Threshold for approval above Rs 10,000.", "Approval required over Rs 40,000.", "10K vs 40K limit"),

        # 21-30: Cancellation & SLA conflicts
        ("cancellation_window", "Orders can be cancelled within 24 hours of placement.", "Cancellation allowed within 48 hours.", "24 vs 48 hours"),
        ("cancellation_window", "Cancel within 12 hours.", "Cancellation window up to 24 hours.", "12 vs 24 hours"),
        ("cancellation_window", "Cancellation accepted within 2 hours.", "Cancel order within 6 hours.", "2 vs 6 hours"),
        ("cancellation_window", "Window of 24 hours to cancel.", "Cancel within 72 hours.", "24 vs 72 hours"),
        ("cancellation_window", "Cancellation allowed within 4 hours.", "Cancel within 24 hours.", "4 vs 24 hours"),
        ("sla_response_time", "First reply response time within 1 hours.", "SLA first reply within 4 hours.", "1 vs 4 hours"),
        ("sla_response_time", "Response time under 2 hours.", "SLA within 24 hours.", "2 vs 24 hours"),
        ("sla_response_time", "Support response time within 30 minutes.", "Response time within 120 minutes.", "30 vs 120 mins"),
        ("restock_window", "Restock returned items within 24 hours.", "Restock returned items in 48 hours.", "24 vs 48 hours"),
        ("restock_window", "Restock returned items within 12 hours.", "Restock in 24 hours.", "12 vs 24 hours"),
    ]

    for idx, (topic, text_a, text_b, desc) in enumerate(topics_and_variants, 1):
        cases.append(
            ConflictBenchmarkCase(
                case_id=f"bench_conf_{idx:03d}",
                topic=topic,
                clause_a_text=text_a,
                clause_b_text=text_b,
                expected_verdict=ConflictVerdict.CONFLICT,
                description=f"Injected Conflict: {desc}",
            )
        )

    # ------------------------------------------------------------------------
    # 30 CONSISTENT PAIRS (Clean, Aligned Rules)
    # ------------------------------------------------------------------------
    clean_pairs = [
        # 1-10: Consistent refund window
        ("refund_window", "Customers are eligible for refund within 7 days of delivery.", "Return request allowed for 7 days.", "7 == 7 days"),
        ("refund_window", "Refund window of 30 days is guaranteed.", "Customer can return within 30 days.", "30 == 30 days"),
        ("refund_window", "Eligible within 14 days.", "Full refund allowed for 14 days.", "14 == 14 days"),
        ("refund_window", "Refund request accepted within 10 days.", "10 days refund window.", "10 == 10 days"),
        ("refund_window", "Items eligible for refund within 7 days.", "Return window of 7 days.", "7 == 7 days"),
        ("refund_window", "Cash refund within 30 days.", "Refund allowed for 30 days.", "30 == 30 days"),
        ("refund_window", "Must claim refund within 15 days.", "Window of 15 days for refund.", "15 == 15 days"),
        ("refund_window", "Eligible within 5 days.", "Return within 5 days.", "5 == 5 days"),
        ("refund_window", "Returns within 21 days.", "Refund permitted within 21 days.", "21 == 21 days"),
        ("refund_window", "Refund window of 7 days.", "7 days return policy.", "7 == 7 days"),

        # 11-20: Consistent approval thresholds
        ("refund_approval_threshold", "Supervisor approval required above Rs 10,000.", "Manager approval needed for amounts exceeding Rs 10,000.", "10K == 10K limit"),
        ("refund_approval_threshold", "Approval required above Rs 25,000.", "Sign-off needed over Rs 25,000.", "25K == 25K limit"),
        ("refund_approval_threshold", "Requires supervisor approval above Rs 10,000.", "Amounts over Rs 10,000 need approval.", "10K == 10K limit"),
        ("refund_approval_threshold", "Approval threshold above Rs 5,000.", "Supervisor review for amounts exceeding Rs 5,000.", "5K == 5K limit"),
        ("refund_approval_threshold", "Escalate refunds above Rs 10,000.", "Supervisor approval needed above Rs 10,000.", "10K == 10K limit"),
        ("refund_approval_threshold", "Approval required over Rs 15,000.", "Amounts exceeding Rs 15,000 need sign-off.", "15K == 15K limit"),
        ("refund_approval_threshold", "Approval required above Rs 50,000.", "Threshold over Rs 50,000.", "50K == 50K limit"),
        ("refund_approval_threshold", "Supervisor review for amounts above Rs 10,000.", "Approval required exceeding Rs 10,000.", "10K == 10K limit"),
        ("refund_approval_threshold", "Approval needed above Rs 20,000.", "Sign-off needed over Rs 20,000.", "20K == 20K limit"),
        ("refund_approval_threshold", "Approval required above Rs 10,000.", "Approval needed over Rs 10,000.", "10K == 10K limit"),

        # 21-30: Consistent cancellation, restock & SLA
        ("cancellation_window", "Cancel order within 24 hours.", "Cancellation allowed within 24 hours.", "24 == 24 hours"),
        ("cancellation_window", "Window of 12 hours to cancel.", "Cancel within 12 hours.", "12 == 12 hours"),
        ("cancellation_window", "Cancellation accepted within 48 hours.", "Cancel within 48 hours.", "48 == 48 hours"),
        ("cancellation_window", "Cancel within 2 hours.", "Cancellation window up to 2 hours.", "2 == 2 hours"),
        ("cancellation_window", "Cancellation allowed within 6 hours.", "Cancel within 6 hours.", "6 == 6 hours"),
        ("sla_response_time", "Response time under 2 hours.", "SLA first reply within 2 hours.", "2 == 2 hours"),
        ("sla_response_time", "Response time within 24 hours.", "SLA within 24 hours.", "24 == 24 hours"),
        ("sla_response_time", "First reply response time within 1 hours.", "SLA within 1 hours.", "1 == 1 hours"),
        ("restock_window", "Restock returned items within 24 hours.", "Restock in 24 hours.", "24 == 24 hours"),
        ("restock_window", "Restock returned items within 48 hours.", "Restock in 48 hours.", "48 == 48 hours"),
    ]

    for idx, (topic, text_a, text_b, desc) in enumerate(clean_pairs, 1):
        cases.append(
            ConflictBenchmarkCase(
                case_id=f"bench_clean_{idx:03d}",
                topic=topic,
                clause_a_text=text_a,
                clause_b_text=text_b,
                expected_verdict=ConflictVerdict.CONSISTENT,
                description=f"Clean Consistent Pair: {desc}",
            )
        )

    return cases


def evaluate_conflict_benchmark(
    detector: PolicyConflictDetector | None = None,
) -> dict[str, Any]:
    """
    Run detector on the 60 ground truth benchmark cases.
    Computes precision, recall, F1, and accuracy.
    """
    det = detector or PolicyConflictDetector()
    cases = build_conflict_benchmark_dataset()

    tp = 0  # True Positives: expected conflict and detected conflict
    fp = 0  # False Positives: expected consistent but detected conflict
    tn = 0  # True Negatives: expected consistent and detected consistent
    fn = 0  # False Negatives: expected conflict but detected consistent

    for c in cases:
        clauses_a = det.extract_clauses_from_text("doc_a", "Doc A", c.clause_a_text)
        clauses_b = det.extract_clauses_from_text("doc_b", "Doc B", c.clause_b_text)
        if not clauses_a or not clauses_b:
            continue

        finding = det.compare_clause_pair(clauses_a[0], clauses_b[0])
        actual_verdict = finding.verdict if finding else ConflictVerdict.CONSISTENT

        if c.expected_verdict == ConflictVerdict.CONFLICT:
            if actual_verdict == ConflictVerdict.CONFLICT:
                tp += 1
            else:
                fn += 1
        elif c.expected_verdict == ConflictVerdict.CONSISTENT:
            if actual_verdict == ConflictVerdict.CONSISTENT:
                tn += 1
            else:
                fp += 1

    total_evaluated = tp + fp + tn + fn
    precision = round((tp / (tp + fp)) * 100, 1) if (tp + fp) > 0 else 100.0
    recall = round((tp / (tp + fn)) * 100, 1) if (tp + fn) > 0 else 100.0
    f1 = round((2 * precision * recall / (precision + recall)), 1) if (precision + recall) > 0 else 100.0
    accuracy = round(((tp + tn) / total_evaluated) * 100, 1) if total_evaluated > 0 else 100.0

    return {
        "total_cases": total_evaluated,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "accuracy": accuracy,
    }
