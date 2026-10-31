# Proofline — Master Implementation Plan
> **Deep Analysis Date:** 2026-10-24  
> **Current State:** 108 tests green, Weeks 1–7 complete (~65% of total Proofline vision)  
> **Tech Stack Decision:** React + Vite (portfolio-grade, premium UI) for Dashboard  
> **Rule:** 100% test pass rate, 0 ruff lint errors, Windows ASCII-safe output always

---

## SECTION 1: CURRENT CODEBASE AUDIT (What Exists & Where)

### Backend Python Package: `src/earp/`

| Module | Files | Key Classes / Functions | Status |
|--------|-------|------------------------|--------|
| `db/` | `models.py`, `session.py` | 12 SQL tables: Customer, Product, Order, OrderItem, Payment, Refund, InventoryLog, SupportTicket, LedgerEntry, TraceRecord, TraceStepRecord, WatchdogFindingRecord | **DONE** |
| `guard/` | `engine.py` | `ActionGuard.evaluate()` — 5 policy checks, ₹10K threshold ASK_HUMAN | **DONE** |
| `trace/` | `schemas.py`, `store.py`, `viewer.py`, `recorder.py` | `Trace`, `TraceStep`, `TraceRecord`, PII-redacted ingest, span tree | **DONE** |
| `replay/` | `engine.py`, `golden.py`, `runner.py` | `ReplayEngine`, `CaseReplayResult`, `GoldenCase`, 50 golden cases in `config/golden_cases.yaml` | **DONE** |
| `evals/` | `metrics.py`, `regression.py`, `ci_gate.py`, `runner.py` | `EvaluationSummary`, `RegressionEngine`, `RegressionReport.cost_delta_usd`, CI gate exit codes | **DONE** |
| `security/` | `pii.py`, `dlp.py`, `redteam/attacks.py`, `redteam/runner.py` | `PIIMasker` (6 Indian PII types), `DLPFilter`, 40-attack red team suite, `RedTeamScorecard` | **DONE** |
| `watchdog/` | `engine.py`, `rules/*.py` (6 rules), `conflicts/detector.py` | `WatchdogEngine`, 6 integrity rules, `PolicyConflictDetector` with 60-pair benchmark | **DONE** |
| `target_app/` | `agent.py`, `llm.py`, `seed.py`, `rag/retriever.py`, `tools/` | `ShopOpsAgent` (LangGraph ReAct), `MockLLM`, Faker seeder, hybrid RAG retriever | **DONE** |
| `gateway/` | `app.py` | FastAPI with 20+ endpoints: Guard, Traces, Evals, Regression, Security, Conflicts, RedTeam | **DONE** |
| `dashboard/` | `__init__.py` only | **EMPTY — needs full build** | **NOT STARTED** |

### Tests: `tests/` — 108 Total Passing

| Test Suite | File | Count | Coverage |
|------------|------|-------|----------|
| `test_agent/test_week3.py` | Agent, RAG, tools | 24 | Week 3 |
| `test_evals/test_week5.py` | Metrics, regression, CI gate | 8 | Week 5 |
| `test_gateway/test_api.py` | All REST endpoints | 6 | Cross-week |
| `test_guard/test_engine.py` | Guard policy checks | 6 | Week 2 |
| `test_replay/test_week4.py` | Replay engine, golden cases | 11 | Week 4 |
| `test_security/test_week6.py` | PII, DLP | 15 | Week 6 |
| `test_redteam/test_week7.py` | 40-attack suite | 12 | Week 7 |
| `test_trace/test_schemas.py` | Trace schemas | 20 | Week 1 |
| `test_watchdog/test_rules.py` | 6 integrity rules | 6 | Weeks 2+6 |

### FastAPI Gateway — Existing Endpoints (`gateway/app.py`)

```
GET  /health
POST /api/v1/traces
GET  /api/v1/traces
GET  /api/v1/traces/stats
GET  /api/v1/traces/{trace_id}
POST /api/v1/guard/check
POST /api/v1/watchdog/scan
GET  /api/v1/watchdog/findings
PATCH /api/v1/watchdog/findings/{id}/resolve
POST /api/v1/evals/run
POST /api/v1/evals/regression
POST /api/v1/security/mask
POST /api/v1/security/inspect
POST /api/v1/conflicts/scan
POST /api/v1/redteam/run
```

CORS already enabled: `allow_origins=["*"]` — React frontend can connect directly.

---

## SECTION 2: GAP ANALYSIS (What Is Missing vs. New Blueprints)

### Priority Classification
- **P0** = Core differentiator, blocks portfolio showcasing
- **P1** = Major feature, needed for completeness
- **P2** = Polish & production hardening
- **P3** = Bonus / Phase 5 (Scout)

---

### GAP-001: React + Vite Dashboard [P0] — NOT STARTED
**What:** Premium dark-mode, glassmorphism React dashboard that consumes the FastAPI backend.  
**Why P0:** This is the visual showcase. Internship interviews = "show me" moment.  
**Pages needed:**
1. **Overview / Platform Health** — Animated KPI cards, live health pulse, recent traces feed
2. **Live Traces** — Trace list with waterfall timeline, span drill-down, input/output diff
3. **Action Guard** — Human approval queue, live block/allow/escalate stats, policy rule breakdown
4. **Watchdog** — Finding cards with severity badges, 1-click resolve button, rule violation breakdown
5. **Regression & Eval** — Accuracy delta chart, P50/P90/P95 latency bar chart, cost breakdown
6. **Red Team Security** — Attack category radar chart, before/after defense comparison, 40-attack matrix
**Stack:** React 18 + Vite + TypeScript + Recharts + React Query (auto-polling every 5s) + Vanilla CSS

---

### GAP-002: Claim-versus-State Verifier [P0] — NOT STARTED
**What:** Proofline's hero differentiator. Agent says "Refund of ₹1,200 processed" — did the `refunds` table actually get a new row?  
**Why P0:** This is the ONE feature nobody else does. It's the core thesis of Proofline.  
**Files needed:**
- `src/earp/evals/claims/schemas.py` — `Claim`, `EvidenceBundle`, `ClaimVerdict`, `VerificationResult`
- `src/earp/evals/claims/extractor.py` — Extract structured claims from agent response text
- `src/earp/evals/claims/verifier.py` — DB before/after snapshot, deterministic comparison
- `src/earp/evals/claims/planted_cases.py` — 30 planted failure scenarios
- `tests/test_evals/test_claims.py` — Tests for all 30 planted cases  
**New API endpoint:** `POST /api/v1/evals/verify-claims`  
**Claim types:** `action` (did DB change?), `fact` (is claim factually correct?), `policy` (matches policy doc?), `status` (correct order/refund status?)  
**Verdicts:** `SUPPORTED`, `CONTRADICTED`, `UNSUPPORTED`, `UNVERIFIABLE`

---

### GAP-003: pass^k Repeat-Trial Runner [P1] — NOT STARTED
**What:** LLMs are non-deterministic. Running a test once is insufficient. Run k=5 times, all must pass.  
**Why P1:** Changes "our eval score is 95%" to "our reliability is 95% with k=5 consistency" — far more rigorous.  
**Files needed:**
- `src/earp/evals/passk.py` — `PassKRunner`, k=5 trials, computes `pass@1`, `pass^k`, `flake_rate`
- `tests/test_evals/test_passk.py`  
**New API endpoint:** `POST /api/v1/evals/passk`

---

### GAP-004: Advanced Watchdog — Statistical Anomaly Detection [P1] — NOT STARTED
**What:** Instead of just rule-based (refund > payment), detect when refund VOLUME is statistically abnormal.  
**Why P1:** Production AI systems need proactive anomaly detection, not just reactive rule checks.  
**Files needed:**
- `src/earp/watchdog/anomaly.py` — `AnomalyDetector` with Z-score + IQR sliding window
- Metrics tracked: Daily refund count, daily refund amount, error rate, avg latency
- Output: `AnomalyAlert` with Z-score value, baseline mean/std, current value, severity  
- `tests/test_watchdog/test_anomaly.py`  
**New API endpoint:** `GET /api/v1/watchdog/anomaly/report`

---

### GAP-005: CRM/ERP Multi-System Reconciliation [P1] — NOT STARTED
**What:** Enterprise systems have multiple downstream records (CRM ticket + ERP order + DB row). Proofline checks all 3 agree.  
**Why P1:** This is the Watchdog's "Level 2" — moves beyond single-table checks to cross-system integrity.  
**Files needed:**
- `src/earp/watchdog/reconcile/` directory
- `src/earp/watchdog/reconcile/engine.py` — `ReconciliationEngine`
- `src/earp/watchdog/reconcile/schemas.py` — `ReconciliationResult`, `ReconciliationFailure`
- 4 failure modes: Missing in CRM, Duplicate in ERP, Wrong field mapping (currency/amount), Stale sync (>15min lag)
- `tests/test_watchdog/test_reconcile.py`  
**New API endpoint:** `POST /api/v1/watchdog/reconcile`

---

### GAP-006: Alerting Pipeline [P1] — NOT STARTED
**What:** When watchdog or anomaly detector fires, notify the right people.  
**Files needed:**
- `src/earp/watchdog/alerts.py` — `AlertDispatcher`, Slack webhook, Email stub, in-memory alert queue
- Deduplication: Same rule+entity gets one alert per hour max (throttle)
- `tests/test_watchdog/test_alerts.py`  
**New API endpoint:** `GET /api/v1/watchdog/alerts`

---

### GAP-007: Human-in-the-Loop Approval Queue [P1] — NOT STARTED
**What:** When Action Guard returns `ASK_HUMAN`, the action is paused. A reviewer must Approve/Reject/Edit before the agent continues.  
**Why P1:** Right now ASK_HUMAN just returns the decision but doesn't actually pause execution. This makes it real.  
**Files needed:**
- DB Table: `approval_queue` (pending, approved, rejected, timeout) — add to `models.py`
- `src/earp/guard/approvals.py` — `ApprovalQueue`, create/update approval requests
- Dashboard: Approval Queue page with Approve/Reject buttons that call API  
**New API endpoints:**
- `GET /api/v1/guard/approvals` — list pending approvals
- `POST /api/v1/guard/approvals/{id}/approve`
- `POST /api/v1/guard/approvals/{id}/reject`

---

### GAP-008: Formal Replay Levels (L0/L1/L2/L3) [P2] — PARTIAL
**What:** Current replay engine runs agent fully (L0). Need explicit level classification.  
**Levels:**
- L0: Fresh agent run (current behavior)
- L1: Stubbed tool responses (deterministic, no side effects)
- L2: L1 + seeded model (same prompt seed for consistency)
- L3: Full snapshot restore (restore DB state to exact pre-trace snapshot)  
**Files needed:**
- `src/earp/replay/levels.py` — `ReplayLevel` enum, level router
- Update `ReplayEngine.replay_case()` to accept `level: ReplayLevel`

---

### GAP-009: Proofline Scout — Black-Box Audit Agent [P3] — NOT STARTED
**What:** Point Scout at ANY external AI chatbot (competitor, client, internal), it runs 12 probe categories and generates a 1-page evidence audit PDF.  
**Why P3:** This is the "outbound sales tool" — run it on a prospect's chatbot, show them findings, convert them to a client.  
**Files needed:**
- `src/earp/scout/scope.py` — `scope.yaml` parser with cryptographic validation, kill switch
- `src/earp/scout/safety.py` — Rate limiter (1 req/5s), auto-stop on 3x 5xx errors
- `src/earp/scout/probes/` — 12 probe category modules
- `src/earp/scout/oracles/` — L1 deterministic + L2 ground truth + L3 self-contradiction + L4 LLM judge
- `src/earp/scout/report.py` — Evidence audit report generator (HTML → PDF)
- `tests/test_scout/` — Tests for each probe and oracle level

---

### GAP-010: Proofline Bench [P2] — NOT STARTED
**What:** 60+ labeled planted-failure cases (the benchmark that measures Proofline's OWN detector quality).  
**Files needed:**
- `bench/` directory
- `bench/cases/` — 60+ labeled cases across all failure taxonomy groups
- `bench/runner.py` — `BenchmarkRunner` computing precision/recall of each detector
- `bench/report.md` — Published benchmark results

---

### GAP-011: Production Deployment Config [P2] — NOT STARTED
**What:** Docker, HTTPS (Caddy), backup/restore scripts, env management.  
**Files needed:**
- `docker-compose.prod.yml` — Production-grade compose (PostgreSQL, Redis, API, UI)
- `Caddyfile` — HTTPS with automatic Let's Encrypt
- `deploy/backup.sh`, `deploy/restore.sh`
- `.env.production.example`

---

### GAP-012: ADR Documentation [P2] — NOT STARTED
**What:** 12 Architecture Decision Records explaining key design choices.  
**Files needed:**
- `docs/adr/ADR-001-database-choice.md`
- `docs/adr/ADR-002-guard-enforcement-model.md`
- ... (ADR-003 through ADR-012)

---

## SECTION 3: IMPLEMENTATION ORDER (Sprint Plan)

### Phase A: Core Differentiators (Portfolio-Critical) — Estimated: 3 Days

```
Day 1 — Sprint A1: Claim-versus-State Verifier (GAP-002)
  - schemas.py (Claim, ClaimVerdict, EvidenceBundle, VerificationResult)
  - extractor.py (regex + NLP claim extraction from agent responses)
  - verifier.py (DB before/after snapshot capture + deterministic comparison)
  - planted_cases.py (30 planted failure scenarios)
  - tests/test_evals/test_claims.py (all 30 cases)
  - API endpoint: POST /api/v1/evals/verify-claims

Day 2 — Sprint A2: pass^k Reliability Runner (GAP-003) + HITL Approval Queue (GAP-007)
  - passk.py (k=5 repeat trials, flake_rate, pass@1 vs pass^k)
  - tests/test_evals/test_passk.py
  - models.py: Add ApprovalQueueRecord table
  - guard/approvals.py (ApprovalQueue CRUD)
  - API endpoints: GET/POST /api/v1/guard/approvals/*

Day 3 — Sprint A3: Advanced Watchdog (GAP-004, GAP-005, GAP-006)
  - watchdog/anomaly.py (Z-score + IQR sliding window)
  - watchdog/reconcile/ (4 CRM/ERP failure modes)
  - watchdog/alerts.py (Slack/Email stub + alert queue)
  - tests/test_watchdog/test_week8.py
  - API endpoints: GET /api/v1/watchdog/anomaly/report, POST /api/v1/watchdog/reconcile, GET /api/v1/watchdog/alerts
```

### Phase B: React + Vite Dashboard (GAP-001) — Estimated: 2-3 Days

```
Day 4 — Sprint B1: Foundation & Scaffolding
  STEP B1.1: Create ui/ directory
    - npx create-vite ui/ --template react-ts
    - Install dependencies: recharts, @tanstack/react-query, axios, react-router-dom
  STEP B1.2: Global design system (ui/src/styles/)
    - CSS variables: dark glassmorphism palette
    - Base typography (Google Fonts: Inter)
    - Component base: Card, Badge, Button, Sidebar, TopBar
    - Animations: fade-in, slide-up, pulse-glow keyframes
  STEP B1.3: Layout shell
    - App.tsx with React Router + sidebar navigation
    - Sidebar with 6 page links + platform logo
    - TopBar with health pulse indicator + timestamp

Day 5 — Sprint B2: Pages 1–3
  STEP B2.1: Page 1 — Platform Overview
    - Animated KPI cards: Total Traces, Avg Latency, Success Rate, Total Cost
    - Live health indicator (polling /health every 5s via React Query)
    - Recent traces mini-feed (last 5 traces)
    - Severity donut chart (watchdog findings by severity)
  STEP B2.2: Page 2 — Live Traces
    - Trace list table with search + filter (workflow_type, status)
    - Click a row → Trace Detail drawer
    - Trace Detail: Input/Output, Waterfall timeline bar, Step-by-step accordion
  STEP B2.3: Page 3 — Action Guard + Approval Queue
    - Guard stats: ALLOW / BLOCK / ASK_HUMAN breakdown (donut chart)
    - Approval Queue table: Pending approvals with Approve/Reject buttons
    - Policy rule trigger frequency bar chart

Day 6 — Sprint B3: Pages 4–6
  STEP B3.1: Page 4 — Watchdog Findings
    - Finding cards grid: severity badge, rule name, entity, description
    - 1-click "Resolve" button (calls PATCH endpoint)
    - Severity breakdown bar chart
    - Anomaly alerts panel (GAP-004)
  STEP B3.2: Page 5 — Regression & Eval
    - Run eval button (POST /api/v1/evals/run) + loading state
    - Accuracy metrics cards: Overall, Intent, Guard, Tool
    - Latency bar chart: P50 / P90 / P95 grouped bars
    - Regression comparison: Baseline vs Candidate accuracy delta
    - Language breakdown table: en/hi/hinglish accuracy
  STEP B3.3: Page 6 — Red Team Security Scorecard
    - Defense improvement hero stat (big number animation)
    - Before vs After comparison cards
    - Category breakdown: radar chart (6 attack categories)
    - Attack matrix table: 40 attacks, baseline result, protected result
```

### Phase C: Production Hardening (P2) — Estimated: 1 Day

```
Day 7 — Sprint C1: Deploy + Docs
  - docker-compose.prod.yml (PostgreSQL, API, UI with Nginx)
  - Caddyfile (HTTPS config)
  - deploy/backup.sh, restore.sh
  - .env.production.example
  - docs/adr/ (12 ADRs)
  - Formal Replay Levels L0/L1/L2/L3 (GAP-008)
```

### Phase D: Proofline Scout (P3) — Estimated: 2 Days

```
Day 8–9 — Sprint D1: Scout Black-Box Agent
  - scope.yaml parser + kill switch
  - Rate limiter + safety controls
  - 12 probe categories
  - 4-tier oracle hierarchy
  - Evidence audit report generator
  - Tests
```

---

## SECTION 4: DETAILED TECHNICAL SPECS

### 4.1 Claim-versus-State Verifier (GAP-002)

```python
# src/earp/evals/claims/schemas.py

class ClaimType(str, Enum):
    ACTION = "action"       # "I issued a refund of ₹1,200"
    FACT = "fact"           # "Your order was placed on 15 Jan"
    POLICY = "policy"       # "Refunds are processed within 5 days"
    STATUS = "status"       # "Your ticket is now resolved"

class ClaimVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"         # DB confirms the claim
    CONTRADICTED = "CONTRADICTED"  # DB contradicts the claim
    UNSUPPORTED = "UNSUPPORTED"    # DB has no evidence either way
    UNVERIFIABLE = "UNVERIFIABLE"  # Cannot check programmatically

class Claim(BaseModel):
    claim_id: str
    claim_type: ClaimType
    subject_entity: str          # "refund", "order", "ticket"
    subject_id: str | None       # Extracted entity ID
    asserted_value: str          # What the agent claimed
    span_text: str               # Exact text from agent response
    span_start: int
    span_end: int

class EvidenceBundle(BaseModel):
    db_before: dict              # DB state snapshot BEFORE agent action
    db_after: dict               # DB state snapshot AFTER agent action
    policy_text: str | None      # Matching policy clause if applicable

class VerificationResult(BaseModel):
    claim: Claim
    verdict: ClaimVerdict
    evidence: EvidenceBundle
    explanation: str
    confidence: float            # 0.0 - 1.0
```

```python
# src/earp/evals/claims/verifier.py

class ClaimVerifier:
    def snapshot_before(self, db: Session, entity_type: str, entity_id: str) -> dict:
        """Capture DB state before agent action."""
        
    def snapshot_after(self, db: Session, entity_type: str, entity_id: str) -> dict:
        """Capture DB state after agent action."""
        
    def verify(
        self,
        claim: Claim,
        evidence: EvidenceBundle,
    ) -> VerificationResult:
        """Deterministic comparison: claimed vs actual DB state."""
```

**30 Planted Failure Scenarios:**
1. False Success (agent says "refund processed" but refunds table has no new row) — 5 variants
2. False Failure (agent says "cannot process" but DB was actually updated) — 5 variants  
3. Omitted Failure (agent says "order cancelled" but status is still "pending") — 5 variants
4. Wrong Entity (agent says "refund for order X" but refund is for order Y) — 5 variants
5. Partial Success (agent says "₹500 refunded" but DB shows ₹250) — 5 variants
6. Async Pending (agent says "processing" but DB shows "completed") — 5 variants

---

### 4.2 pass^k Runner (GAP-003)

```python
# src/earp/evals/passk.py

@dataclass
class PassKResult:
    case_id: str
    k: int
    pass_at_1: bool         # Did the first trial pass?
    pass_k: bool            # Did ALL k trials pass?
    pass_count: int         # How many of k trials passed?
    flake_rate: float       # % of trials that flipped result
    trial_results: list[bool]

class PassKRunner:
    def run(
        self,
        cases: list[GoldenCase],
        llm: LLMProtocol,
        k: int = 5,
    ) -> list[PassKResult]:
        """Run each case k times, return pass^k metrics."""
```

---

### 4.3 Anomaly Detection (GAP-004)

```python
# src/earp/watchdog/anomaly.py

class AnomalyMethod(str, Enum):
    Z_SCORE = "z_score"     # (current - mean) / std > 2.5
    IQR = "iqr"             # current > Q3 + 1.5 * IQR

@dataclass
class AnomalyAlert:
    metric: str             # "daily_refund_count", "daily_refund_amount", "error_rate"
    current_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    method: AnomalyMethod
    severity: str           # "low", "medium", "high", "critical"
    window_days: int        # Sliding window used

class AnomalyDetector:
    def __init__(self, window_days: int = 30, z_threshold: float = 2.5):
        ...
    
    def compute_refund_anomalies(self, db: Session) -> list[AnomalyAlert]:
        """Check if today's refund volume is statistically abnormal."""
    
    def compute_latency_anomalies(self, db: Session) -> list[AnomalyAlert]:
        """Check if today's avg latency is abnormally high."""
    
    def compute_error_rate_anomalies(self, db: Session) -> list[AnomalyAlert]:
        """Check if today's error rate is statistically elevated."""
    
    def full_report(self, db: Session) -> dict:
        """Run all anomaly checks and return consolidated report."""
```

---

### 4.4 React Dashboard Architecture

```
ui/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── public/
│   └── favicon.ico
└── src/
    ├── main.tsx               -- Entry: React Query provider + Router
    ├── App.tsx                -- Root: Sidebar + <Outlet/>
    ├── api/
    │   ├── client.ts          -- axios instance (baseURL = localhost:8000)
    │   └── hooks/             -- React Query hooks for each API endpoint
    │       ├── useHealth.ts
    │       ├── useTraces.ts
    │       ├── useGuard.ts
    │       ├── useWatchdog.ts
    │       ├── useEvals.ts
    │       └── useRedTeam.ts
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.tsx    -- Navigation with active route highlighting
    │   │   ├── TopBar.tsx     -- Platform status + timestamp
    │   │   └── PageWrapper.tsx
    │   ├── ui/
    │   │   ├── Card.tsx       -- Glassmorphism card container
    │   │   ├── Badge.tsx      -- Severity/status badge
    │   │   ├── Button.tsx     -- Action button with loading state
    │   │   ├── Spinner.tsx    -- Loading spinner
    │   │   ├── MetricCard.tsx -- KPI card with icon + animated number
    │   │   └── EmptyState.tsx -- Empty data placeholder
    │   └── charts/
    │       ├── LatencyChart.tsx   -- Grouped bar: P50/P90/P95
    │       ├── SeverityDonut.tsx  -- Donut: watchdog severity breakdown
    │       ├── AccuracyBar.tsx    -- Horizontal bar: accuracy by workflow
    │       └── RadarChart.tsx     -- Red team category radar
    ├── pages/
    │   ├── Overview.tsx       -- Page 1: Platform health dashboard
    │   ├── Traces.tsx         -- Page 2: Live trace list + detail drawer
    │   ├── Guard.tsx          -- Page 3: Guard stats + approval queue
    │   ├── Watchdog.tsx       -- Page 4: Findings + anomaly alerts
    │   ├── Evals.tsx          -- Page 5: Regression + eval metrics
    │   └── RedTeam.tsx        -- Page 6: Security scorecard
    └── styles/
        ├── global.css         -- Reset + CSS variables
        ├── components.css     -- Component styles
        └── animations.css     -- Keyframe animations
```

**CSS Design Tokens:**
```css
:root {
  /* Colors: Deep space dark + electric accent */
  --bg-primary: #0a0e1a;
  --bg-surface: rgba(255, 255, 255, 0.04);
  --bg-elevated: rgba(255, 255, 255, 0.08);
  --border: rgba(255, 255, 255, 0.1);
  --accent-primary: #6c63ff;     /* Electric violet */
  --accent-secondary: #00d4ff;   /* Cyan */
  --accent-success: #00e676;     /* Neon green */
  --accent-warning: #ffab40;     /* Amber */
  --accent-danger: #ff5252;      /* Red */
  --text-primary: #e8eaf6;
  --text-secondary: rgba(232, 234, 246, 0.6);
  
  /* Glassmorphism */
  --glass-bg: rgba(255, 255, 255, 0.05);
  --glass-border: rgba(255, 255, 255, 0.12);
  --glass-blur: blur(20px);
  
  /* Shadows */
  --shadow-card: 0 8px 32px rgba(0, 0, 0, 0.4);
  --shadow-glow-violet: 0 0 20px rgba(108, 99, 255, 0.3);
  
  /* Spacing */
  --space-xs: 4px; --space-sm: 8px; --space-md: 16px;
  --space-lg: 24px; --space-xl: 32px; --space-2xl: 48px;
  
  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

---

### 4.5 New API Endpoints to Add

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `/api/v1/evals/verify-claims` | POST | Claim-vs-State verification | A1 |
| `/api/v1/evals/passk` | POST | pass^k reliability runner | A2 |
| `/api/v1/guard/approvals` | GET | List pending human approvals | A2 |
| `/api/v1/guard/approvals/{id}/approve` | POST | Approve a queued action | A2 |
| `/api/v1/guard/approvals/{id}/reject` | POST | Reject a queued action | A2 |
| `/api/v1/watchdog/anomaly/report` | GET | Statistical anomaly report | A3 |
| `/api/v1/watchdog/reconcile` | POST | CRM/ERP reconciliation scan | A3 |
| `/api/v1/watchdog/alerts` | GET | List triggered alerts | A3 |

---

## SECTION 5: RULES & CONSTRAINTS (Never Violate These)

1. **Windows ASCII Safety:** No raw Unicode emojis or box-drawing chars in CLI output. Use `[PASS]`, `[FAIL]`, `[GATE]`, `[WARNING]`, `[INFO]` tags.
2. **Zero Lint Errors:** Every Python file must pass `ruff check` with current `pyproject.toml` config before commit.
3. **100% Test Pass Rate:** New code = new tests. Never break existing 108.
4. **Pydantic v2:** Use `model_dump()` not `.dict()`, use `model_validate()` not `.parse_obj()`.
5. **Domain Agnostic:** No ShopOps-specific logic in platform modules. PII masker, Guard, Watchdog, Trace work for ANY domain.
6. **Typed Python:** All functions must have type annotations. No `Any` unless absolutely necessary.
7. **No Hardcoded Secrets:** Use `.env` + `python-dotenv` for API keys, DB URLs.
8. **React Dashboard:** TypeScript strict mode, no `any` types, React Query for all data fetching (no raw useEffect + fetch).
9. **CORS:** FastAPI already has `allow_origins=["*"]`. React dev server on port 5173, API on port 8000.
10. **Test Files:** One test file per feature module. Clear, descriptive test names. Fixture-based setup.

---

## SECTION 6: IMPLEMENTATION SEQUENCE (Step-by-Step Execution)

### IMMEDIATE NEXT (Day 1 — Sprint A1)

**Step 1:** Create `src/earp/evals/claims/` package
- `__init__.py`
- `schemas.py` — All Pydantic models
- `extractor.py` — Claim extraction from response text
- `verifier.py` — DB snapshot + comparison logic
- `planted_cases.py` — 30 planted failure test scenarios

**Step 2:** Add `POST /api/v1/evals/verify-claims` endpoint to `gateway/app.py`

**Step 3:** Create `tests/test_evals/test_claims.py` (all 30 planted cases must pass)

**Step 4:** Run `ruff check src/` — fix all lint errors before moving on

---

### THEN (Day 2 — Sprint A2)

**Step 5:** Create `src/earp/evals/passk.py` + `tests/test_evals/test_passk.py`

**Step 6:** Add `approval_queue` table to `src/earp/db/models.py`

**Step 7:** Create `src/earp/guard/approvals.py` + `tests/test_guard/test_approvals.py`

**Step 8:** Add 3 new approval endpoints to `gateway/app.py`

---

### THEN (Day 3 — Sprint A3)

**Step 9:** Create `src/earp/watchdog/anomaly.py` + tests

**Step 10:** Create `src/earp/watchdog/reconcile/` + tests

**Step 11:** Create `src/earp/watchdog/alerts.py` + tests

**Step 12:** Add 3 new watchdog endpoints to `gateway/app.py`

---

### THEN (Days 4–6 — Sprint B: Dashboard)

**Step 13:** Scaffold Vite React app in `ui/` directory

**Step 14:** Build global CSS design system

**Step 15:** Build layout shell (Sidebar, TopBar, Router)

**Step 16:** Build Page 1 (Overview) + API hooks

**Step 17:** Build Page 2 (Traces) + waterfall chart

**Step 18:** Build Page 3 (Guard + Approval Queue)

**Step 19:** Build Page 4 (Watchdog)

**Step 20:** Build Page 5 (Evals + Regression)

**Step 21:** Build Page 6 (Red Team)

**Step 22:** Polish: animations, responsive layout, loading states, empty states

---

### THEN (Day 7 — Sprint C)

**Step 23:** Production Docker config

**Step 24:** ADR documentation (12 files)

**Step 25:** Formal Replay Levels L0/L1/L2/L3

---

## SECTION 7: PROGRESS TRACKER

| # | Feature | Phase | Status | Tests | Notes |
|---|---------|-------|--------|-------|-------|
| 1 | DB Models (12 tables) | Foundation | DONE | ✓ | Week 1 |
| 2 | Action Guard (5 policies) | Guard | DONE | ✓ | Week 2 |
| 3 | Trace Store + Schemas | Trace | DONE | ✓ | Week 1 |
| 4 | ShopOps Agent (LangGraph) | Agent | DONE | ✓ | Week 3 |
| 5 | RAG Retriever + Citations | RAG | DONE | ✓ | Week 3 |
| 6 | Replay Engine (50 golden) | Replay | DONE | ✓ | Week 4 |
| 7 | Eval Metrics + Regression | Evals | DONE | ✓ | Week 5 |
| 8 | CI Gate | CI/CD | DONE | ✓ | Week 5 |
| 9 | PII Masker (6 types) | Security | DONE | ✓ | Week 6 |
| 10 | DLP Filter | Security | DONE | ✓ | Week 6 |
| 11 | Watchdog 6 Rules | Watchdog | DONE | ✓ | Week 6 |
| 12 | Policy Conflict Detector | Watchdog | DONE | ✓ | Week 7 |
| 13 | Red Team 40-Attack Suite | Security | DONE | ✓ | Week 7 |
| 14 | FastAPI Gateway (20+ endpoints) | API | DONE | ✓ | Cross-week |
| 15 | **Claim-vs-State Verifier** | **Evals** | **TODO** | - | GAP-002, P0 |
| 16 | **pass^k Runner** | **Evals** | **TODO** | - | GAP-003, P1 |
| 17 | **Human Approval Queue** | **Guard** | **TODO** | - | GAP-007, P1 |
| 18 | **Anomaly Detection** | **Watchdog** | **TODO** | - | GAP-004, P1 |
| 19 | **CRM/ERP Reconciliation** | **Watchdog** | **TODO** | - | GAP-005, P1 |
| 20 | **Alerting Pipeline** | **Watchdog** | **TODO** | - | GAP-006, P1 |
| 21 | **React + Vite Dashboard (6 pages)** | **UI** | **TODO** | - | GAP-001, P0 |
| 22 | **Formal Replay Levels** | **Replay** | **TODO** | - | GAP-008, P2 |
| 23 | **Production Docker** | **Deploy** | **TODO** | - | GAP-011, P2 |
| 24 | **ADR Documentation** | **Docs** | **TODO** | - | GAP-012, P2 |
| 25 | **Proofline Scout** | **Scout** | **TODO** | - | GAP-009, P3 |
| 26 | **Proofline Bench** | **Bench** | **TODO** | - | GAP-010, P2 |

**Current:** 14/26 features complete (~54% by feature count, ~65% by complexity weight)  
**Target:** 24/26 by end of implementation (Scout + Bench are bonus P3)

---

## SECTION 8: FILES TO CREATE (Full List)

```
Backend Python:
├── src/earp/evals/claims/__init__.py
├── src/earp/evals/claims/schemas.py
├── src/earp/evals/claims/extractor.py
├── src/earp/evals/claims/verifier.py
├── src/earp/evals/claims/planted_cases.py
├── src/earp/evals/passk.py
├── src/earp/guard/approvals.py
├── src/earp/watchdog/anomaly.py
├── src/earp/watchdog/reconcile/__init__.py
├── src/earp/watchdog/reconcile/schemas.py
├── src/earp/watchdog/reconcile/engine.py
├── src/earp/watchdog/alerts.py
├── src/earp/replay/levels.py                  (formal replay levels)
└── [UPDATE] src/earp/db/models.py             (add ApprovalQueueRecord)
└── [UPDATE] src/earp/gateway/app.py           (8 new endpoints)

Tests:
├── tests/test_evals/test_claims.py
├── tests/test_evals/test_passk.py
├── tests/test_guard/test_approvals.py
└── tests/test_watchdog/test_week8.py

React Frontend (new ui/ directory):
├── ui/package.json
├── ui/vite.config.ts
├── ui/tsconfig.json
├── ui/index.html
├── ui/src/main.tsx
├── ui/src/App.tsx
├── ui/src/api/client.ts
├── ui/src/api/hooks/ (6 hook files)
├── ui/src/components/layout/ (3 files)
├── ui/src/components/ui/ (6 files)
├── ui/src/components/charts/ (4 files)
├── ui/src/pages/ (6 page files)
└── ui/src/styles/ (3 CSS files)

Deploy & Docs:
├── docker-compose.prod.yml
├── Caddyfile
├── deploy/backup.sh
├── deploy/restore.sh
├── .env.production.example
└── docs/adr/ (12 ADR files)
```

---

*Plan created: 2026-10-24 | Author: Antigravity (Proofline Master Architect)*  
*Next action: Start Sprint A1 — Claim-versus-State Verifier*
