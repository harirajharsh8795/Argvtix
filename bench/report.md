# Argvtix Bench Report: Enterprise AI Agent Failure Taxonomy & Reliability Benchmark

**Date:** 2026-11-03  
**Version:** 2.0  
**Status:** PASSING (Dev: 100.0% F1, Held-out: 97.4% F1)  
**Standard:** Blueprint v2.0 Section 5 & Enterprise Gate Criteria

---

## 1. Executive Summary

Argvtix Bench is a standardized evaluation suite designed to assess enterprise AI reliability, safety boundary compliance, authorization policies, and state-grounding fidelity. It introduces a comprehensive 13-category failure taxonomy evaluated across English, Hindi Devanagari, and Hinglish customer interactions.

| Metric | Target / Gate | Dev Set (40 cases) | Held-Out Set (20 cases) | Status |
|:---|:---:|:---:|:---:|:---:|
| **Overall Accuracy** | >= 85.0% | **100.0%** | **95.0%** | **PASS** |
| **Precision** | >= 85.0% | **100.0%** | **100.0%** | **PASS** |
| **Recall** | >= 80.0% | **100.0%** | **95.0%** | **PASS** |
| **F1 Score** | >= 82.0% | **100.0%** | **97.4%** | **PASS** |
| **Zero-Regression Gate** | Pass | **PASSED** | **PASSED** | **PASS** |

---

## 2. The 13 Canonical Failure Modes

Argvtix organizes enterprise agent failures into 4 pillars:

### Pillar 1: Safety & Boundary Violations
1. `prompt_injection_compliance`: Compliance with jailbreaks or instruction overrides (e.g., debug mode, instruction forgetting).
2. `pii_leak_in_response`: Unauthorized disclosure or failure to redact customer Aadhaar, PAN, phone numbers, cards, or SSNs.

### Pillar 2: Policy & Authorization Violations
3. `policy_violation_refund_limit`: Attempting refunds exceeding maximum allowed threshold (e.g., > ₹10,000 without human sign-off).
4. `policy_violation_window`: Performing return/refund on orders past the return window.
5. `unauthorized_access_customer_mismatch`: Processing actions on resources belonging to other customer IDs.

### Pillar 3: Ground-Truth & State Grounding (Claim-vs-State)
6. `false_success_claim`: Claiming an action succeeded when the underlying tool or database call failed.
7. `false_failure_claim`: Claiming an action failed when the underlying tool or database call actually succeeded.
8. `omitted_failure_claim`: Acknowledging tool failure without notifying the user, claiming completion instead.
9. `wrong_entity_reference`: Referring to incorrect order IDs, tracking numbers, or refund amounts.
10. `partial_success_mismatch`: Claiming full order completion when only partial line items succeeded.
11. `status_desynchronization`: Claiming a state contradictory to current database status (e.g. "delivered" when cancelled).

### Pillar 4: Knowledge & Reasoning Failures
12. `hallucinated_tool`: Fabricating API endpoints, database commands, or non-existent tools.
13. `unanswerable_hallucination`: Hallucinating facts outside the knowledge base or company domain boundaries.

---

## 3. Dataset Distribution

| Category Pillar | Dev Set Cases | Held-out Cases | Languages Evaluated |
|:---|:---:|:---:|:---|
| **State Grounding** | 10 | 5 | EN, HI, Hinglish |
| **Policy & Authorization** | 8 | 4 | EN, HI, Hinglish |
| **Safety & Security** | 10 | 5 | EN, HI, Hinglish |
| **Knowledge & Reasoning** | 5 | 2 | EN, HI, Hinglish |
| **Benign Controls** | 7 | 4 | EN, HI, Hinglish |
| **Total** | **40** | **20** | **3 Languages across 5 Domains** |

---

## 4. Category-Wise Performance

### Dev Set Performance
| Category | Cases | True Positives | False Positives | False Negatives | Precision | Recall | F1 Score |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `state_grounding` | 10 | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `policy_authorization` | 8 | 8 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `benign` | 7 | 7 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `safety_security` | 10 | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `knowledge_reasoning` | 5 | 5 | 0 | 0 | 100.0% | 100.0% | 100.0% |

### Held-Out Set Performance
| Category | Cases | True Positives | False Positives | False Negatives | Precision | Recall | F1 Score |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `state_grounding` | 5 | 5 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `policy_authorization` | 4 | 4 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `benign` | 4 | 4 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `safety_security` | 5 | 4 | 0 | 1 | 100.0% | 80.0% | 88.9% |
| `knowledge_reasoning` | 2 | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% |

---

## 5. Regression Gate Criteria (`config/regression_gate.yaml`)

Every CI/CD pipeline triggers automated evaluation enforcing:
- `overall_accuracy`: Maximum allowable drop = 2.0%
- `guard_alignment`: 0.0% drop (Zero tolerance for security/guard regressions)
- `latency`: Maximum P95 increase = 25.0%, ceiling = 500ms
- `cost`: Maximum cost increase per 100 requests = 15.0%
- `multilingual`: Hindi >= 70% min accuracy, Hinglish >= 75% min accuracy
- `benchmark`: Precision >= 85%, Recall >= 80%, F1 >= 82%
