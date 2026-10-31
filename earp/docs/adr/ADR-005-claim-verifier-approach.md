# ADR-005: Claim-vs-State Verifier — LLM Extraction + DB Tool Snapshots

## Status
Accepted (Blueprint Correction Applied)

## Context
AI agents often hallucinate outcomes: claiming an action was completed when a tool failed (False Success), claiming an action failed when the DB write succeeded (False Failure), or omitting tool failure entirely.
Regex-based claim extraction is brittle across diverse phrasing styles in multilingual or natural language conversations.

## Decision
We implemented a two-stage Claim-vs-State Verifier:
1. **Structured LLM Claim Extractor:** Uses structured Pydantic schemas (`Claim`, `ClaimType`, `ExtractionAccuracyReport`) to extract factual assertions from agent responses. Extraction accuracy is calibrated and measured independently before verifier scoring.
2. **Deterministic Database Snapshot Comparison:** Claims are compared directly against the actual rows mutated by tool executions in the trace (not merely request parameter IDs).
3. **Planted Failure Taxonomy:** Verified against 30 planted cases across 6 distinct categories: False Success, False Failure, Omitted Failure, Wrong Entity, Partial Success, and Status Mismatch.

## Consequences
- **Positive:** Catches silent agent hallucinations with mathematical precision; eliminates regex brittleness.
- **Trade-off:** Small token cost overhead during eval runs for LLM structured extraction.
