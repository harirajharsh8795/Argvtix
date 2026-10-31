# ADR-004: Formal Replay Levels (L0, L1, L2, L3) and Determinism

## Status
Accepted (Blueprint Correction Applied)

## Context
When an AI agent fails in production, developers must reproduce the failure. However, re-running an agent against live third-party APIs or fluctuating vector indexes introduces non-determinism and side effects (e.g. duplicate refunds or altered retrieval results).

## Decision
We established 4 standardized Replay Levels:
1. **L0 (Live Agent):** Live tools, live RAG retrieval, live LLM. Non-deterministic, causes real side effects.
2. **L1 (Tool Stubs):** Tool responses are replayed from recorded trace outputs. No DB writes, but retrieval and LLM remain live.
3. **L2 (Deterministic Replay):** L1 + **stubbed retrieval results** (from original trace chunks) + **seeded model parameters**. Guaranteed deterministic, zero side effects.
4. **L3 (Snapshot Restore):** Database restored to pre-trace state via transactional savepoints, then executed under L2.

Every replay output must carry explicit `replay_level: ReplayLevel` and `is_deterministic: bool` tags.

## Consequences
- **Positive:** Enables 100% reproducible debugging of tricky agent regressions without mutating production ledgers or drifting vector embeddings.
- **Trade-off:** Recorded traces must preserve retrieved text chunks and tool payloads.
