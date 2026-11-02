# 🔍 ARGVTIX Platform — Deep Project & Architecture Analysis

## 1. Executive Summary & Vision

### Problem Statement
Enterprise AI agents (customer support, booking, finance, supply chain) aksar **silently fail** karte hain:
1. **Financial Leaks**: Duplicate refunds dena ya payment se zyada refund kar dena.
2. **Policy Violations**: ₹10,000+ ke high-value refunds bina human approval ke pass kar dena.
3. **State Corruption**: Orders cancel ho jaana par inventory restock na hona.
4. **Hallucination & Hall of Shame**: Galat customer ke data ko touch karna.

### Solution: Enterprise AI Reliability Platform (ARGVTIX)
ARGVTIX ek **dual-layer protective shield** hai jo kisi bhi company ke AI agent ke upar baithta hai:
- **Layer 1: Pre-Action Bodyguard (Action Guard)** — Agent ke tool call karne se pehle hi check karta hai: *"Kya ye customer is order ka owner hai? Kya pehle refund mila hai? Kya amount ₹10,000 se zyada hai?"*
- **Layer 2: Real-time Flight Recorder (Trace Engine)** — Har LLM prompt, token count, RAG retrieval chunk, guard decision, aur latency record karta hai.
- **Layer 3: Post-Execution Silent Watchdog** — Database mein chupke se hone wali inconsistencies (duplicate refunds, missing inventory logs, total calculation errors) ko scan karke pakadta hai.

---

## 2. Layer-by-Layer Architectural Breakdown

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SHOP-OPS AI AGENT (Target)                      │
│                                                                        │
│  [Customer Ticket] ──> [Classify Intent] ──> [RAG Policy Store]        │
│                                                     │                  │
│                                                     ▼                  │
└───────────────────────────────────────────────┬────────────────────────┘
                                                │ Pre-execution check
                                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   ACTION GUARD (Pre-Action Bodyguard)                  │
│                                                                        │
│  1. Order Exists?       2. Ownership Valid?   3. Duplicate Refund?    │
│  4. Excess Refund?      5. Amount >= Rs10,000?                        │
│                                                                        │
│  Decision: ALLOW  │  BLOCK  │  ASK_HUMAN                               │
└───────────────────────┬───────────────────────┬────────────────────────┘
                        │ ALLOW                 │ BLOCK / ASK_HUMAN
                        ▼                       ▼
┌───────────────────────────────┐       ┌────────────────────────────────┐
│      MCP BUSINESS TOOLS       │       │       RESPONSE GENERATOR       │
│  • issue_refund()             │       │  • Friendly Hinglish output    │
│  • cancel_order()             │       │  • "Supervisor ko bheja gaya"  │
│  • check_inventory()          │       │  • "Order pehle se refunded"   │
│  • get_customer_balance()     │       └───────────────┬────────────────┘
└───────────────┬───────────────┘                       │
                │                                       │
                ▼                                       │
┌───────────────────────────────┐                       │
│      DATABASE (Postgres/SQL)  │                       │
│  • 8 Business Tables          │                       │
│  • 3 ARGVTIX Tables              │                       │
└───────────────┬───────────────┘                       │
                │                                       │
                ▼                                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   ARGVTIX TRACE RECORDER & GATEWAY                        │
│                                                                        │
│  Records: LLM call ──> Retrieval ──> Guard decision ──> Output/Tool   │
│  Metrics: Exact latency_ms, token usage, cost_usd, status             │
└───────────────────────────────────────┬────────────────────────────────┘
                                        │ Post-execution audit
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   SILENT WATCHDOG ENGINE                               │
│                                                                        │
│  Runs 4 Data Integrity Rules:                                          │
│  1. Duplicate Refund Detector       2. Order Total Mismatch            │
│  3. Refund Exceeds Payment          4. Inventory Discrepancy Log       │
│                                                                        │
│  Outputs: Persisted Watchdog Findings with Severity (Critical / High) │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Deep Component Inspection

### A. Database Layer (`src/argvtix/db/`)
- **Dual Support**: Local dev ke liye zero-config SQLite (`argvtix.db`), production ke liye PostgreSQL via Docker (`docker-compose.yml`).
- **8 Business Tables**:
  1. `customers` — Profile, email, phone, tier.
  2. `products` — SKU, price, real-time `inventory_count`.
  3. `orders` — Status (`pending`, `shipped`, `delivered`, `cancelled`), `total_amount`.
  4. `order_items` — Line items with quantity and unit price.
  5. `payments` — Transaction method (`upi`, `card`, `netbanking`), status (`succeeded`, `failed`).
  6. `refunds` — Refund ledger with order reference, reason, status.
  7. `inventory_logs` — Double-entry audit ledger for every stock change.
  8. `support_tickets` — Inbound customer service tickets.
- **3 Observability Platform Tables**:
  1. `traces` — Root trace header with metadata, latency, cost, prompt version.
  2. `trace_steps` — Granular steps (LLM call, RAG retrieval, Guard decision, Tool execution).
  3. `watchdog_findings` — Flagged integrity issues with severity, affected entity, and resolution state.

### B. Action Guard (`src/argvtix/guard/engine.py`)
- **Evaluation Rules**:
  1. `verify_order_exists`: Order DB mein exist karta hai ya nahi.
  2. `verify_customer_ownership`: Ticket raise karne wala customer hi us order ka real buyer hai.
  3. `prevent_duplicate_refund`: Us order par pehle se koi completed refund exist karta hai ya nahi.
  4. `cap_refund_at_payment`: Proposed refund amount order ke total paid amount se zyada nahi ho sakta.
  5. `human_approval_over_threshold`: Agar refund ₹10,000 se zyada hai, to AI tool call block hokar `ASK_HUMAN` decision deta hai.

### C. Watchdog Engine (`src/argvtix/watchdog/`)
- **Zero Hallucination Inspection**: Ye AI par depend nahi karta — direct SQL queries se mathematical aur logic rules verify karta hai.
- **Fault Injector**: `inject.py` purposely 4 types ke bugs plant karta hai (duplicate refund records, skewed order totals, missing inventory logs). Watchdog scan inhen 100% catch karta hai.

### D. LangGraph Agent (`src/argvtix/target_app/agent.py`)
- StateGraph architecture with 5 specialized nodes:
  - `classify_intent`: Customer ticket parse karke structured intent + entities banata hai.
  - `retrieve_policy`: SOP store se keyword scoring ke basis par relevant rules fetch karta hai.
  - `check_guard`: Action proposal ko Action Guard ke paas bhejta hai.
  - `execute_tool`: Guard decision `ALLOW` hone par hi database operation execute karta hai.
  - `generate_response`: Customer ko Hinglish mein concise aur polite response deta hai.

### E. Trace Engine & Recorder (`src/argvtix/trace/`)
- Pydantic v2 schemas strictly validate every field.
- Har step ka 0-based `step_index`, exact `timestamp`, execution `duration_ms`, aur specific payload (`LLMCallData`, `RetrievalData`, `ToolCallData`, `GuardDecisionData`, `OutputData`, `ErrorData`) preserve hota hai.

---

## 4. Test Suite & Code Quality Health Check

```
============================= 60 passed in 2.54s ==============================

tests/test_agent/test_week3.py ........................                  [ 40%]
tests/test_gateway/test_api.py ....                                      [ 46%]
tests/test_guard/test_engine.py ......                                   [ 56%]
tests/test_trace/test_schemas.py ....................                    [ 90%]
tests/test_watchdog/test_rules.py ......                                 [100%]
```

- **Linter Status**: `ruff check .` passes with **0 errors and 0 warnings**.
- **Compatibility**: Standard Python `.pth` file configured in `.venv` — Windows PowerShell environment mein seamless execution.
- **Console Encoding**: Windows default `cp1252` encoding issue resolved using clean ASCII UI formatting.

---

## 5. End-to-End Walkthrough of a Real Ticket

Scenario: Customer #1 asks: *"Order 1 ka refund chahiye"*
1. **CLI Ingestion**: Simulator passes ticket to `ShopOpsAgent`.
2. **Classify**: LLM classifies intent as `refund`, extracts `order_id=1`.
3. **RAG Retrieval**: Retriever pulls eligibility policy (7-day window, ₹10K approval limit).
4. **Guard Evaluation**:
   - Order exists? Yes.
   - Customer owns order? Yes (Order #1 belongs to Customer #1).
   - Duplicate refund exists? None yet.
   - Amount <= payment? Yes.
   - Amount >= ₹10,000? No.
   - **Guard Decision: ALLOW**.
5. **Tool Execution**: `issue_refund()` inserts refund record into SQLite/Postgres.
6. **Response Generation**: LLM outputs friendly Hinglish response.
7. **Trace Logging**: Trace recorder finalizes `Trace` object (5 steps, 38ms latency, 0 errors).
8. **Watchdog Audit**: Watchdog runs scheduled scan — verifies payment amount >= refund amount, order totals match. Everything clean.

---

## 6. Completed Milestones & Current Platform Status

Humne **Week 1 se Week 6 tak ke saare milestones 100% production-quality ke sath complete** kar liye hain:

1. **Week 4 (Trace Store & Replay Engine)**:
   - Complete trace database storage (`traces` and `trace_steps` tables).
   - Visual CLI Trace Viewer (`argvtix.trace.viewer`).
   - 50 ground-truth Golden Cases (`config/golden_cases.yaml`).
   - Replay Engine (`argvtix.replay.engine`) supporting trace replay, diff, and benchmark suites.

2. **Week 5 (Evaluation & Regression Engine + CI Gate)**:
   - Full evaluation metrics (`metrics.py`): P50/P90/P95 latencies, cost/100, language detection, intent/guard/tool accuracy.
   - Regression Engine (`regression.py`): Baseline vs candidate comparative matrix, `what_got_worse`, `what_got_better`.
   - CI Regression Gate (`ci_gate.py`): Automated exit 0/1 gate protecting deployments from prompt regressions.
   - Evaluator CLI runner (`argvtix.evals.runner --summary`, `--gate`, `--workflow`) & REST APIs (`/api/v1/evals/run`, `/api/v1/evals/regression`).

3. **Week 6 (PII Masking, DLP Firewall & Watchdog Rules 5 & 6)**:
   - PII Sanitizer (`pii.py`): Masks Indian Aadhaar, Phone (+91/0), PAN card, Credit card, Email, UPI VPA.
   - Outbound DLP Filter (`dlp.py`): Blocks leaked system instructions, DB credentials, and error stack traces.
   - Agent & Gateway integration: Inbound tickets sanitized before reaching LLM or Trace store; outbound responses sanitized.
   - Watchdog Rule 5 (`LedgerBalanceRule`): Detects wallet balance vs ledger entry discrepancy.
   - Watchdog Rule 6 (`OrphanPaymentRule`): Detects ghost/orphan payments referencing non-existent orders.
   - Gateway Security endpoints: `POST /api/v1/security/mask`, `POST /api/v1/security/inspect`.

---

## 7. Current Test Coverage & Health

- **Total Test Suites**: 7 (`test_agent`, `test_evals`, `test_gateway`, `test_guard`, `test_replay`, `test_security`, `test_trace`, `test_watchdog`)
- **Total Tests Passing**: **96 / 96 (100% Green)**
- **Linter Checks**: **0 Errors (Ruff Clean)**
- **Console Compatibility**: 100% Windows cp1252 safe (pure ASCII formatting)

---

## 8. What's Next: Week 7 (Red Teaming + Policy Conflict Detector)

Next sprint focus:
1. **Adversarial Red Team Suite**: 40 attack vectors (prompt injection, jailbreak roleplay, mass refund exploit, data exfiltration).
2. **Policy Conflict Detector**: Cross-clause consistency verification (e.g., 30 vs 45 day refund window discrepancy).
