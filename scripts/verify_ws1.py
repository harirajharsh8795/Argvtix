"""
WS-1 Verification Script: Contamination Audit & Honest Benchmarking.

Outputs verified artifacts:
- artifacts/verification/ws1_contamination_audit.json
- artifacts/verification/ws1_sealed_benchmark.json
- artifacts/verification/ws1_claim_extractor_metrics.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from argvtix.evals.claims.extractor import ClaimExtractor
from bench.runner import BenchmarkRunner

OUTPUT_DIR = REPO_ROOT / "artifacts" / "verification"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_git_sha() -> str:
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def verify_contamination() -> dict:
    git_sha = get_git_sha()
    # Check commits touching extractor and cases
    res = subprocess.run(
        ["git", "log", "--oneline", "--", "src/argvtix/evals/claims/extractor.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    commits = res.stdout.strip().splitlines()

    audit_result = {
        "workstream": "WS-1",
        "task": "Contamination Audit",
        "command": "python scripts/verify_ws1.py --contamination",
        "git_sha": git_sha,
        "date": datetime.now(UTC).isoformat(),
        "model": "deterministic-git-audit",
        "held_out_status": "CONTAMINATED",
        "declaration": (
            "Prior held-out set (bench/cases/held_out_set.yaml) is officially declared CONTAMINATED. "
            "Git history reveals that commit 4820226 and commit 0cd84cf modified "
            "src/argvtix/evals/claims/extractor.py by injecting Hindi/Hinglish domain vocabulary "
            "(e.g., 'डिलीवर', 'इनिशिएट', 'क्रेडिट', 'update kar diya') after reviewing held-out failures."
        ),
        "post_creation_extractor_commits": commits,
        "remediation": (
            "A completely new, frozen 60-case SEALED benchmark set has been created under "
            "bench/cases/sealed/sealed_set.yaml with sha256 checksum frozen before running."
        ),
    }

    out_file = OUTPUT_DIR / "ws1_contamination_audit.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audit_result, f, indent=2)
    print(f"[WS-1] Contamination audit saved to {out_file}")
    return audit_result


def verify_sealed_benchmark() -> dict:
    git_sha = get_git_sha()
    sealed_file = REPO_ROOT / "bench" / "cases" / "sealed" / "sealed_set.yaml"
    checksum_file = REPO_ROOT / "bench" / "cases" / "sealed" / "checksum.sha256"

    with open(sealed_file, "rb") as f:
        computed_hash = hashlib.sha256(f.read()).hexdigest().upper()

    with open(checksum_file, encoding="utf-8") as f:
        expected_hash = f.read().strip().upper()

    if computed_hash != expected_hash:
        raise ValueError(f"Sealed set checksum mismatch! {computed_hash} != {expected_hash}")

    runner = BenchmarkRunner()
    report = runner.run("sealed")

    artifact = {
        "workstream": "WS-1",
        "task": "Sealed Benchmark Evaluation",
        "command": "python bench/runner.py --split sealed",
        "git_sha": git_sha,
        "date": datetime.now(UTC).isoformat(),
        "model": "rule-and-policy-detectors",
        "sealed_sha256": computed_hash,
        "checksum_verified": True,
        "total_cases": report.total_cases,
        "overall_accuracy": report.overall_accuracy,
        "overall_precision": report.overall_precision,
        "overall_recall": report.overall_recall,
        "overall_f1": report.overall_f1,
        "false_positive_rate": report.false_positive_rate,
        "passes_gate": report.passes_gate,
        "category_metrics": {k: v.model_dump() for k, v in report.category_metrics.items()},
        "failure_count": len(report.failure_details),
        "failure_details": report.failure_details,
    }

    out_file = OUTPUT_DIR / "ws1_sealed_benchmark.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"[WS-1] Sealed benchmark report saved to {out_file}")
    return artifact


def verify_claim_extractor_recall() -> dict:
    git_sha = get_git_sha()
    extractor = ClaimExtractor()

    # 30 carefully curated statements for precision/recall evaluation:
    # 15 positive statements (asserting concrete factual state transitions)
    # 15 negative/neutral control statements (no state claims)
    labeled_cases = [
        # Positive statements (expect >= 1 claim)
        {
            "id": "p01",
            "text": "I have refunded $45.00 back to your credit card.",
            "has_claim": True,
            "domain": "ecommerce",
            "lang": "en",
        },
        {
            "id": "p02",
            "text": "Your order #8921 has been cancelled successfully.",
            "has_claim": True,
            "domain": "ecommerce",
            "lang": "en",
        },
        {
            "id": "p03",
            "text": "Maine aapka payment initiate kar diya hai, 24 ghante me credit hoga.",
            "has_claim": True,
            "domain": "banking",
            "lang": "hinglish",
        },
        {
            "id": "p04",
            "text": "Ticket #5543 has been escalated to Tier-3 Technical Engineering.",
            "has_claim": True,
            "domain": "saas",
            "lang": "en",
        },
        {
            "id": "p05",
            "text": "Aapka package DEL-9823 successfully deliver ho gaya hai.",
            "has_claim": True,
            "domain": "logistics",
            "lang": "hinglish",
        },
        {
            "id": "p06",
            "text": "हमने ₹1,500 का रिफंड प्रोसेस कर दिया है।",
            "has_claim": True,
            "domain": "banking",
            "lang": "hi",
        },
        {
            "id": "p07",
            "text": "The refund of $120.00 failed due to an expired debit card.",
            "has_claim": True,
            "domain": "banking",
            "lang": "en",
        },
        {
            "id": "p08",
            "text": "Delivery attempt for shipment SHP-443 failed: customer was unavailable.",
            "has_claim": True,
            "domain": "logistics",
            "lang": "en",
        },
        {
            "id": "p09",
            "text": "Account ACC-901 has been temporarily suspended due to security flags.",
            "has_claim": True,
            "domain": "banking",
            "lang": "en",
        },
        {
            "id": "p10",
            "text": "Database backup completed successfully at 04:00 UTC.",
            "has_claim": True,
            "domain": "saas",
            "lang": "en",
        },
        {
            "id": "p11",
            "text": "Aapki order request cancel kardi gayi hai.",
            "has_claim": True,
            "domain": "ecommerce",
            "lang": "hinglish",
        },
        {
            "id": "p12",
            "text": "आपका टिकट TKT-889 बंद कर दिया गया है।",
            "has_claim": True,
            "domain": "saas",
            "lang": "hi",
        },
        {
            "id": "p13",
            "text": "We have credited 50 loyalty points to your customer wallet.",
            "has_claim": True,
            "domain": "ecommerce",
            "lang": "en",
        },
        {
            "id": "p14",
            "text": "Payment of ₹4,200 has been transferred to beneficiary account.",
            "has_claim": True,
            "domain": "banking",
            "lang": "hinglish",
        },
        {
            "id": "p15",
            "text": "Item SKU-990 stock has been updated to 0 in warehouse B.",
            "has_claim": True,
            "domain": "ecommerce",
            "lang": "en",
        },
        # Negative/Neutral statements (expect 0 claims)
        {
            "id": "n01",
            "text": "Hello! Welcome to ShopOps customer support. How can I assist you today?",
            "has_claim": False,
            "domain": "general",
            "lang": "en",
        },
        {
            "id": "n02",
            "text": "Namaste, main aapki kya sahayata kar sakta hoon?",
            "has_claim": False,
            "domain": "general",
            "lang": "hinglish",
        },
        {
            "id": "n03",
            "text": "Could you please provide your 10-digit registered mobile number?",
            "has_claim": False,
            "domain": "banking",
            "lang": "en",
        },
        {
            "id": "n04",
            "text": "I understand your frustration and am looking into the matter.",
            "has_claim": False,
            "domain": "general",
            "lang": "en",
        },
        {
            "id": "n05",
            "text": "कृपया थोड़ा प्रतीक्षा करें, मैं जानकारी जांच रहा हूँ।",
            "has_claim": False,
            "domain": "general",
            "lang": "hi",
        },
        {
            "id": "n06",
            "text": "Our refund policy allows returns within 30 days of purchase.",
            "has_claim": False,
            "domain": "ecommerce",
            "lang": "en",
        },
        {
            "id": "n07",
            "text": "Thank you for contacting ACME IT Service Desk.",
            "has_claim": False,
            "domain": "saas",
            "lang": "en",
        },
        {
            "id": "n08",
            "text": "Kya aap mujhe order number bata sakte hain?",
            "has_claim": False,
            "domain": "ecommerce",
            "lang": "hinglish",
        },
        {
            "id": "n09",
            "text": "Have a great day ahead! Let us know if you need anything else.",
            "has_claim": False,
            "domain": "general",
            "lang": "en",
        },
        {
            "id": "n10",
            "text": "To reset your password, please click the link sent to your email.",
            "has_claim": False,
            "domain": "saas",
            "lang": "en",
        },
        {
            "id": "n11",
            "text": "We take data privacy and customer security very seriously.",
            "has_claim": False,
            "domain": "banking",
            "lang": "en",
        },
        {
            "id": "n12",
            "text": "धन्यवाद! आपका दिन शुभ हो।",
            "has_claim": False,
            "domain": "general",
            "lang": "hi",
        },
        {
            "id": "n13",
            "text": "I will check with our fulfillment partner and get back to you.",
            "has_claim": False,
            "domain": "logistics",
            "lang": "en",
        },
        {
            "id": "n14",
            "text": "Please make sure your app is updated to version 2.4.",
            "has_claim": False,
            "domain": "saas",
            "lang": "en",
        },
        {
            "id": "n15",
            "text": "Sorry for the delay in response due to high queue volumes.",
            "has_claim": False,
            "domain": "general",
            "lang": "en",
        },
    ]

    tp = 0
    fp = 0
    fn = 0
    tn = 0
    eval_details = []

    for item in labeled_cases:
        extracted = extractor.extract_claims(item["text"])
        detected_claim = len(extracted) > 0
        expected_claim = item["has_claim"]

        if expected_claim and detected_claim:
            tp += 1
            status = "TP"
        elif not expected_claim and detected_claim:
            fp += 1
            status = "FP"
        elif expected_claim and not detected_claim:
            fn += 1
            status = "FN"
        else:
            tn += 1
            status = "TN"

        eval_details.append(
            {
                "id": item["id"],
                "text": item["text"],
                "expected_claim": expected_claim,
                "detected_claims_count": len(extracted),
                "status": status,
            }
        )

    precision = round((tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 100.0, 2)
    recall = round((tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 100.0, 2)
    f1 = round(
        (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0, 2
    )
    specificity = round((tn / (tn + fp) * 100.0) if (tn + fp) > 0 else 100.0, 2)

    artifact = {
        "workstream": "WS-1",
        "task": "Claim Extractor Precision and Recall Evaluation",
        "command": "python scripts/verify_ws1.py --extractor",
        "git_sha": git_sha,
        "date": datetime.now(UTC).isoformat(),
        "model": "deterministic-regex-fallback",
        "total_cases": len(labeled_cases),
        "positive_cases": sum(1 for c in labeled_cases if c["has_claim"]),
        "negative_control_cases": sum(1 for c in labeled_cases if not c["has_claim"]),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "specificity": specificity,
        "cases_evaluated": eval_details,
    }

    out_file = OUTPUT_DIR / "ws1_claim_extractor_metrics.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"[WS-1] Claim extractor metrics saved to {out_file}")
    return artifact


if __name__ == "__main__":
    verify_contamination()
    verify_sealed_benchmark()
    verify_claim_extractor_recall()
