# ADR-003: Trace Schema Design — OpenTelemetry-Aligned Step Waterfall

## Status
Accepted

## Context
AI agents execute multi-turn, multi-step graphs combining LLM generation, tool calls, vector retrieval, and guard evaluation. Traditional web request logs fail to represent step dependencies, token spend, latency distributions, and intermediate state changes.

## Decision
We designed a hierarchical OpenTelemetry-compatible trace schema:
- `Trace`: Top-level transaction containing `trace_id`, `session_id`, `project_id`, `workflow`, `status`, `total_latency_ms`, `user_input`, `agent_response`.
- `TraceStep`: Individual execution nodes tagged with `StepType` (`LLM`, `TOOL`, `GUARD`, `RETRIEVAL`, `OUTPUT`).
- Token & Cost Metrics: Each LLM step tracks prompt tokens, completion tokens, and model identifier for continuous spend telemetry.
- PII Tokenization: Trace ingestion automatically sanitizes customer identifiers (Aadhaar, PAN, Card digits, Phone) before persistence.

## Consequences
- **Positive:** Enables step waterfall visualization in UI, sub-millisecond step latency auditing, exact reproduction during replay, and automated claims verification.
- **Trade-off:** Storage overhead is higher than flat request logging; mitigated by PostgreSQL indexing and retention policies.
