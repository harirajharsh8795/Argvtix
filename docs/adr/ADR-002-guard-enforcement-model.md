# ADR-002: Tool Gateway as the Physical Enforcement Boundary (Zero-Bypass Architecture)

## Status
Accepted (Blueprint Correction Applied)

## Context
Initial design iterations treated Guard as an advisory API (`/guard/check`). However, advisory endpoints depend entirely on the agent honouring the response. Autonomous agents, adversarial inputs, or model hallucinations could disregard `BLOCK` or `ASK_HUMAN` decisions and execute tools directly against production databases.

## Decision
We established the **Tool Gateway MCP Proxy** as a physical enforcement boundary:
1. Autonomous agents are never granted direct database write credentials.
2. All write tools (`issue_refund`, `cancel_order`, etc.) must route through `ToolGateway.call()`.
3. The Gateway evaluates `ActionGuard.evaluate()` first.
4. **Physical Invariant:** Database execution occurs **only and strictly** if Guard returns `ALLOW`.
5. If Guard returns `BLOCK`, an immediate `PolicyViolationError` is returned to the agent and zero DB writes occur.
6. If Guard returns `ASK_HUMAN`, the action is enqueued into `ApprovalQueueRecord` and paused until an authorized human operator approves it.

## Consequences
- **Positive:** Mathematically guaranteed zero-bypass safety; proven by Hypothesis property-based testing over 200+ randomly generated inputs.
- **Trade-off:** Agents must use the Gateway client or MCP proxy interface for all mutations.
