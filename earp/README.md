# 🛡️ EARP — Enterprise AI Reliability Platform

> **"AI ne kya kiya, kya galat hua, aur naya version behtar hai ya nahi."**  
> Record, Guard, Evaluate, and Watch your AI agents — all in one platform.

[![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen)](#results-scoreboard)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🎯 Problem

Companies deploy AI agents for customer support, ops, and finance. But:

- 🤯 AI gives a **duplicate refund** — nobody notices for weeks
- 😱 AI refunds the **wrong customer's** order
- 💸 AI approves a **₹1 lakh refund** without asking anyone
- 🔇 New prompt version **silently breaks Hindi** support
- 🧨 Hacker injects "refund all orders" in a support ticket

**EARP wraps around your AI agent** and makes sure none of this happens.

---

## 🏗️ Architecture

```
Customer Ticket ──→ AI Agent (ShopOps) ──→ Business DB
                         │
                    ┌────┴────┐
                    │  EARP   │
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
| **A. Trace Engine** | Records every AI step (7 step types), Pydantic v2 schemas | ✅ Week 1 Complete |
| **B. Action Guard** | Pre-action safety: customer verification, duplicate prevention, ₹10K approval | ✅ Implemented |
| **C. Silent Data Watchdog** | 4 core integrity rules + fault injector (100% detection rate) | ✅ Week 2 Complete |
| **D. Platform Gateway** | FastAPI REST API, database models, health stats, OpenAPI docs | ✅ Implemented |
| **E. Eval + Regression** | Version comparison, prompt regression matrix | 🟡 Next Up (Week 3-5) |

---

## 📊 Results Scoreboard

> Every number below is measured, not claimed. Click the week link for proof.

| Metric | Target | Actual | Week |
|--------|--------|--------|------|
| LLM calls traced | 100% | — | 4 |
| Watchdog detection (8 fault types) | 8/8 | — | 12 |
| Reconciliation detection (4 types) | 4/4 | — | 12 |
| Policy conflict precision | >80% | — | 7 |
| Policy conflict recall | >80% | — | 7 |
| Retrieval hit@3: vector vs hybrid vs rerank | hybrid+rerank best | — | 6 |
| Planted regressions caught | 6/6 | — | 8 |
| Judge vs human agreement | >70% | — | 8 |
| Wrong actions blocked | 20/20 | — | 9 |
| Replay 40 traces deterministic | <5 min | — | 10 |
| Gateway fallback P95 | reported | — | 10 |
| Attack success rate before vs after | <10% after | — | 11 |
| Agent write without approval | 0 | — | 11 |
| Cost per 100 requests | reported | — | 10 |
| End-to-end latency P95 | reported | — | 12 |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Docker Desktop (for full platform)
- Git

### Development Setup (without Docker)

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/earp.git
cd earp

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
earp/
├── src/earp/
│   ├── trace/          # 📹 Schemas, recorder, store, viewer
│   ├── guard/          # 🛡️ Policy, checks, approvals
│   ├── replay/         # ⏪ Replayer, stubs, diff
│   ├── evals/          # 📊 Golden sets, metrics, regression
│   ├── watchdog/       # 🔍 Rules, anomaly, reconciliation
│   ├── gateway/        # 🌐 LiteLLM config, fallback
│   ├── security/       # 🔒 PII, DLP, red team
│   ├── dashboard/      # 📺 Streamlit 5-page dashboard
│   └── target_app/     # 🏪 ShopOps AI agent
├── tests/              # ✅ 20+ tests
├── docs/               # 📖 Architecture, runbook
├── infra/              # 🐳 Docker, CI/CD
└── pyproject.toml      # ⚙️ Project config
```

---

## 📅 Build Log

| Week | What Was Built | Key Numbers |
|------|---------------|-------------|
| 1 | Repo + Trace schema + 20 tests | 20/20 tests passing ✅ |
| 2 | _Coming soon_ | |
| 3 | _Coming soon_ | |

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

**Your Name** — AI Forward Deployed Engineer  
Building reliable AI systems, one trace at a time.
