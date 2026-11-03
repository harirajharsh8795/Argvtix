# 🛡️ ARGVTIX — Enterprise AI Reliability Platform

> **"AI ne kya kiya, kya galat hua, aur naya version behtar hai ya nahi."**  
> Record, Guard, Evaluate, and Watch your AI agents — all in one platform.

[![Tests](https://img.shields.io/badge/tests-419%20passing-brightgreen)](#results-scoreboard)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178c6)](https://www.typescriptlang.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🎯 Problem

Companies deploy AI agents for customer support, ops, and finance. But:

- 🤯 AI gives a **duplicate refund** — nobody notices for weeks
- 😱 AI refunds the **wrong customer's** order
- 💸 AI approves a **₹1 lakh refund** without asking anyone
- 🔇 New prompt version **silently breaks Hindi** support
- 🧨 Hacker injects "refund all orders" in a support ticket

**ARGVTIX wraps around your AI agent** and makes sure none of this happens.

---

## 🏗️ Architecture

```
Customer Ticket ──→ AI Agent (ShopOps) ──→ Business DB
                         │
                    ┌────┴────┐
                    │  ARGVTIX   │
                    │         │
                    │ 📹 Trace    — Record every step
                    │ 🛡️ Guard    — Block risky actions
                    │ 📊 Eval     — Compare versions
                    │ 🔍 Watchdog — Catch data bugs
                    │ 📺 Dashboard — See everything
                    │         │
                    └─────────┘
```

| Module | What It Does | Status |
|--------|-------------|--------|
| **A. Trace Engine** | Records every AI step (7 step types), Pydantic v2 schemas, OTel export | ✅ Complete |
| **B. Action Guard** | Pre-action safety: customer verification, duplicate prevention, ₹10K approval | ✅ Complete |
| **C. Silent Data Watchdog** | 6 core integrity rules, ledger reconciliation & statistical IQR anomalies | ✅ Complete |
| **D. Platform Gateway** | FastAPI REST & WS, JWT RBAC, Tenant isolation, rate limiting | ✅ Complete |
| **E. Eval + Regression** | Argvtix Bench (60 cases), Claim-vs-State Verifier, pass^k reliability | ✅ Complete |

---

## 📊 Results Scoreboard

> Every number below is measured, not claimed. Click the week link for proof.

| Metric | Target | Actual | Week / Source |
|--------|--------|--------|---------------|
| Automated Test Pass Rate | 100% | **419 / 419 passed (100%)** | `pytest tests/` |
| Trace Engine Coverage | 100% | **100% (7 step types)** | `tests/test_trace/` |
| Watchdog Detection (DB Integrity) | 100% | **6/6 rules verified** | `tests/test_watchdog/` |
| Reconciliation Detection | 100% | **4/4 discrepancies caught** | `tests/test_watchdog/` |
| Bench Overall Accuracy (Dev) | >= 85% | **100.0%** | `bench/runner.py` |
| Bench Overall Accuracy (Held-out) | >= 85% | **95.0%** | `bench/runner.py` |
| Bench Precision (Dev / Held-out) | >= 85% | **100.0% / 100.0%** | `bench/runner.py` |
| Bench Recall (Dev / Held-out) | >= 80% | **100.0% / 95.0%** | `bench/runner.py` |
| Unauthorized / Wrong Actions Blocked | 100% | **20/20 blocked** | `tests/property/` |
| Unapproved DB Writes Permitted | 0 | **0** | `tests/test_independent_audit.py` |
| Cross-Tenant Query Isolation | 100% | **100% (404 on cross-tenant)** | `tests/test_security/` |
| Tenant Scoped Endpoints | 100% | **10/10 endpoints gated** | `tests/test_security/` |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Docker Desktop (for full platform)
- Git

### Development Setup (without Docker)

```bash
# Clone
git clone https://github.com/harirajharsh8795/Argvtix.git
cd argvtix

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/
```

### Full Platform (with Docker)

```bash
# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Start everything
docker compose up

# Open dashboard
# http://localhost:8501
```

---

## 🧪 Sample Trace

```json
{
  "trace_id": "tr-a1b2c3d4e5f6",
  "input_text": "order 1042 ka refund de do, item kharab tha",
  "prompt_version": "v3",
  "model_version": "gemini-2.0-flash",
  "status": "completed",
  "steps": [
    {
      "step_type": "llm_call",
      "llm_call": {
        "model": "gemini-2.0-flash",
        "input_tokens": 450,
        "output_tokens": 120,
        "cost_usd": 0.002,
        "latency_ms": 1200
      }
    },
    {
      "step_type": "retrieval",
      "retrieval": {
        "query": "refund policy damaged item",
        "method": "hybrid_rerank",
        "chunk_ids": ["policy_chunk_7", "policy_chunk_12"],
        "scores": [0.92, 0.87]
      }
    },
    {
      "step_type": "guard_decision",
      "guard_decision": {
        "action": "issue_refund",
        "decision": "allow",
        "checks_passed": ["ownership", "duplicate", "limit"]
      }
    },
    {
      "step_type": "tool_call",
      "tool_call": {
        "tool_name": "issue_refund",
        "tool_args": {"order_id": 1042, "amount": 2500},
        "is_success": true,
        "is_write": true
      }
    },
    {
      "step_type": "output",
      "output": {
        "response_text": "Amit ji, aapke order #1042 ka ₹2,500 refund process ho gaya hai.",
        "language": "hinglish"
      }
    }
  ],
  "total_tokens": 570,
  "total_cost_usd": 0.002,
  "total_latency_ms": 1462
}
```

---

## 📁 Project Structure

```
argvtix/
├── src/argvtix/
│   ├── trace/          # 📹 Schemas, recorder, store, viewer
│   ├── guard/          # 🛡️ Policy, checks, approvals
│   ├── replay/         # ⏪ Replayer, stubs, diff
│   ├── evals/          # 📊 Golden sets, metrics, regression
│   ├── watchdog/       # 🔍 Rules, anomaly, reconciliation
│   ├── gateway/        # 🌐 LiteLLM config, fallback
│   ├── security/       # 🔒 PII, DLP, red team
│   ├── dashboard/      # 📺 Streamlit 5-page dashboard
│   └── target_app/     # 🏪 ShopOps AI agent
├── tests/              # ✅ 419 tests (100% passing)
├── docs/               # 📖 Architecture, runbook
├── infra/              # 🐳 Docker, CI/CD
└── pyproject.toml      # ⚙️ Project config
```

---

## 📅 Build Log

| Milestone | What Was Built | Key Numbers |
|-----------|---------------|-------------|
| Core Platform | Trace Engine, Action Guard, Watchdog Rules, Gateway REST & WS | 328 tests passing ✅ |
| Staging & Concurrency | Atomic Idempotency, Playwright Browser E2E, Load Benchmarks | 403 tests passing ✅ |
| Step 1 Security Hardening | Tenant Isolation, RBAC on 10 open routes, Token Hardening | 417 tests passing ✅ |
| Step 2 Honest UI & Dynamic Bench | Zero hardcoded metrics, DataUnavailable state, Dynamic bench/report.md | 419 tests passing ✅ |

---

## 🤝 Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Language | Python 3.12, Pydantic v2 | Type safety, validation |
| API | FastAPI | Async, auto-docs |
| Database | Postgres + pgvector | Vector search + relational |
| Agent | LangGraph + MCP | State machine + tool protocol |
| LLMs | Gemini, Groq, Ollama | Free tiers, local option |
| Gateway | LiteLLM | Routing, fallback, cost |
| Eval | RAGAS + custom metrics | Industry standard |
| Security | Presidio | PII detection |
| Dashboard | Streamlit | Rapid prototyping |
| CI/CD | GitHub Actions + Docker | Automated testing |

---

## 📜 License

MIT — use it, learn from it, build on it.

---

## 👤 Author

**Harsh Rawat** (@harirajharsh8795) — AI Platform & Security Engineer  
Building reliable AI systems, one trace at a time.
