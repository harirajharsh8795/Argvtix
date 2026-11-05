# Argvtix Threat Model & Security Architecture

**Document Version:** 1.0.0  
**Target System:** Argvtix Enterprise AI Reliability Platform  
**Architecture:** Python 3.12 (FastAPI), SQLAlchemy (PostgreSQL / SQLite), React 19 + Vite  
**Standard:** STRIDE Methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)

---

## 1. System Overview & Core Assets

Argvtix is an enterprise-grade reliability, security, policy governance, and observability platform for autonomous AI agents. The platform intercepts, audits, reconciles, and evaluates agent tool execution in real-time.

### Primary Assets

| Asset ID | Asset Name | Description | Sensitivity |
| :--- | :--- | :--- | :--- |
| **A-1** | **Customer PII & Financial Identifiers** | Aadhaar numbers, PAN cards, phone numbers, email addresses, credit cards, UPI handles ingested via user chat or agent tool arguments. | Critical / Confidential |
| **A-2** | **Execution Traces & Transcripts** | Step-by-step agent thoughts, prompt text, tool parameters, database outputs, and retrieved document chunks. | High / Confidential |
| **A-3** | **Action Guard Policies & Thresholds** | Financial velocity caps, refund limits ($10,000 threshold), idempotency keys, and human-in-the-loop triggers. | High / Integrity |
| **A-4** | **Database Records & Business State** | Orders, payments, customer balances, refunds, and support tickets in PostgreSQL. | Critical / Integrity |
| **A-5** | **Signing Keys & Credentials** | JWT Secret Key (`ARGVTIX_JWT_SECRET`), LLM provider API keys (`GEMINI_API_KEY`, etc.), Cloudflare Turnstile secrets. | Critical / Confidential |
| **A-6** | **Scout Probe Suites & Audit Findings** | Security vulnerability assessments, reproducibility scores, and regression test reports. | High / Confidential |

---

## 2. Trust Boundaries & Data Flow

```
[ External User / Client Browser ]
                │
         (1) HTTPS / WSS (TLS 1.3)
                ▼
┌────────────────────────────────────────────────────────┐
│ Boundary 1: Perimeter / Network Ingress                │
│  - Cloudflare Turnstile (Anti-Bot Verification)        │
│  - SecurityHeadersMiddleware (CSP, HSTS, X-Frame-Deny) │
│  - MaxPayloadSizeMiddleware (5MB Request Cap)          │
│  - Rate Limiter (SlowAPI / Redis Token Bucket)         │
└──────────────────────────────────────┬─────────────────┘
                                       │
                                (2) Inbound Request
                                       ▼
┌────────────────────────────────────────────────────────┐
│ Boundary 2: API Gateway & Control Plane (FastAPI)      │
│  - Default-Deny Authentication (Bearer JWT HS256)      │
│  - RBAC: ADMIN > OPERATOR > VIEWER                     │
│  - Brute-Force Lockout Defense (5 attempts -> 15m)     │
│  - In-Flight Token Revocation Verification             │
│  - Canonical ARGVTIX_* Config Enforcement              │
└──────────────────┬───────────────────┬─────────────────┘
                   │                   │
    (3) Authenticated Execution     (4) Tool Call Proposal
                   ▼                   ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ Boundary 3: Tenant Layer     │ │ Boundary 4: Guard & Gateway  │
│  - TenantScopedSession       │ │  - Action Guard Policy Check │
│  - Automatic project_id      │ │  - Idempotency Deduplication │
│    query & write injection   │ │  - Approval Queue Enqueue    │
│  - PostgreSQL Row-Level      │ │  - ToolGateway Process       │
│    Security (RLS) Policies   │ │    Boundary Isolation        │
└──────────────┬───────────────┘ └──────────────┬───────────────┘
               │                                │
        (5) DB Queries                   (6) External Tools
               ▼                                ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ Managed PostgreSQL Database  │ │ External APIs / MCP Services │
│ (RLS Protected Tables)       │ │ (Shop Tools, CRM, Payment)   │
└──────────────────────────────┘ └──────────────────────────────┘
```

---

## 3. STRIDE Threat Analysis & Mitigations

### 3.1 Spoofing (Identity & Authenticity)
- **Threat T-1: Token Forgery or Weak Secret Hijacking.** An adversary brute-forces weak default JWT keys to forge Admin tokens.
  - *Mitigation:* `get_jwt_secret_key()` enforces a minimum 32-character secret in production and rejects known development strings (`argvtix_enterprise_secret_dev_key_change_in_prod`, etc.). Short token expiration (2 hours) limits replay windows.
- **Threat T-2: Brute-Force Password Guessing.** Repeated automated attacks against `/api/v1/auth/token`.
  - *Mitigation:* `FailedLoginTracker` enforces exponential lockout after 5 consecutive failures per account/IP for 900 seconds (15 minutes).
- **Threat T-3: Turnstile Challenge Bypass.** Automated bot submission of contact/demo requests.
  - *Mitigation:* Cloudflare Turnstile token validation plus invisible honeypot field verification on public forms.

### 3.2 Tampering (Data Integrity)
- **Threat T-4: Cross-Tenant Data Tampering.** Tenant B updates, resolves, or deletes Watchdog findings or approvals belonging to Tenant A.
  - *Mitigation:* `TenantScopedSession` automatically injects `project_id == current_tenant` on all ORM queries and rejects cross-tenant entity modifications. PostgreSQL Row-Level Security (`FORCE ROW LEVEL SECURITY`) enforces this at the storage engine level.
- **Threat T-5: Replay Attacks & Double Refunds.** Agent or adversary invokes `issue_refund` multiple times with the same parameters.
  - *Mitigation:* Unique database index on `refunds.idempotency_key` coupled with ToolGateway idempotency verification guarantees that duplicate refund requests return cached results with zero duplicate transactions.

### 3.3 Repudiation
- **Threat T-6: Unaudited Human Approvals.** Operator approves a high-value action ($25,000 refund) and denies doing so.
  - *Mitigation:* `ApprovalQueueRecord` immutably captures `reviewer_id`, `decided_at` UTC timestamp, and `reviewer_notes`. Structured audit logs emit signed log events for every approval and rejection.

### 3.4 Information Disclosure (Confidentiality)
- **Threat T-7: Cross-Project Trace Leakage.** Tenant B queries `/api/v1/traces/{trace_id}` belonging to Tenant A.
  - *Mitigation:* Direct query filtering returns an explicit HTTP 404 Not Found (zero information leakage, not 403 Forbidden).
- **Threat T-8: PII Leakage in Transcripts & External LLM Prompts.** Sensitive customer identifiers (Aadhaar, PAN, credit card numbers, UPI) transmitted to external LLM providers.
  - *Mitigation:* Outbound `DLPFilter` and inbound `PIIMasker` redact sensitive entities with typed tokens (`[AADHAAR_...]`, `[PAN_...]`, `[PHONE_...]`) before external dispatch.
- **Threat T-9: System Prompt and Credential Exfiltration.** Malicious prompt injection extracts internal policies or database passwords.
  - *Mitigation:* DLP inspector scans outbound text for regex patterns of AWS keys, database URLs, and policy document phrases.

### 3.5 Denial of Service (Availability)
- **Threat T-10: Memory Exhaustion via Large Payloads.** Adversary streams multi-gigabyte JSON payloads into trace ingestion endpoints.
  - *Mitigation:* `MaxPayloadSizeMiddleware` enforces a strict 5MB body size threshold at the ASGI middleware level, returning HTTP 413 Entity Too Large prior to memory buffering.
- **Threat T-11: Rate Limit Exhaustion & Scout Runaway Probing.** Scout audit runs unbounded loops against target services.
  - *Mitigation:* `ScoutSafetyController` implements sliding-window rate limiters, per-conversation turn caps, circuit breakers on consecutive errors, and an emergency kill switch (`/api/v1/scout/abort`) that halts all active probes in under 5 seconds.

### 3.6 Elevation of Privilege (Authorization)
- **Threat T-12: Viewer Role Escalation to Operator/Admin.** User with `viewer` role accesses evaluation triggering, red-team benchmarks, or approval decision endpoints.
  - *Mitigation:* Strict RBAC hierarchy (`require_role(Role.OPERATOR)`) applied across all state-mutating and sensitive computation endpoints. Automated test suite dynamically verifies the full FastAPI route authorization matrix.
- **Threat T-13: Insecure Development Mode in Production.** `ARGVTIX_ALLOW_INSECURE_DEV_AUTH=true` accidentally enabled in production.
  - *Mitigation:* `verify_credentials()` explicitly refuses insecure dev authentication if `ENVIRONMENT` is `production` or `staging`, failing closed with a critical security alert.

---

## 4. Security Invariants & Compliance Table

| Invariant ID | Rule Description | Enforcement Layer | Proving Test |
| :--- | :--- | :--- | :--- |
| **INV-1** | Tenant project isolation | `TenantScopedSession` & PostgreSQL RLS | `test_auth_matrix.py::TestTenantScopedSession` |
| **INV-2** | Default-deny RBAC on all routes | FastAPI Depends + Route Introspector | `test_auth_matrix.py::TestDynamicAuthorizationMatrix` |
| **INV-3** | Brute-force login lockout | `FailedLoginTracker` (5 strikes / 15m) | `test_auth_matrix.py::TestBruteForceAndLockout` |
| **INV-4** | Token revocation | In-memory / distributed revocation set | `test_auth_matrix.py::TestTokenRevocation` |
| **INV-5** | High-entropy secret in prod | `get_jwt_secret_key()` length check | `test_step1_security_hardening.py` |
| **INV-6** | Idempotent high-value refunds | `ToolGateway` + DB unique index | `test_step4_enforcement.py` |
| **INV-7** | Scout out-of-scope egress block | `validate_scope_allows_request` | `test_target_adapters_and_runtime_egress.py` |

---

## 5. Residual Risk & Operational Recommendations

1. **Distributed Secret Storage:** In multi-node production clusters, replace local environment variables with cloud secret managers (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager).
2. **Distributed Revocation Cache:** When scaling beyond a single replica, back `_revoked_tokens` and `FailedLoginTracker` with Redis rather than in-process memory.
3. **Database Connection Encryption:** Ensure PostgreSQL connections enforce `sslmode=verify-full` in production deployments.
