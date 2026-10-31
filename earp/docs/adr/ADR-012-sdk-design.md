# ADR-012: Proofline SDK Design — Zero-Friction `@trace` and Tool Gateway Integration

## Status
Accepted (Missing Item Added)

## Context
External AI development teams using frameworks like LangGraph, CrewAI, AutoGen, or custom Python agents need an effortless way to integrate Proofline without rewriting their core business logic or adopting intrusive dependencies.

## Decision
We engineered `proofline-sdk` as an independent, pip-installable library:
1. **`@trace` Decorator:**
   - Single-line auto-instrumentation supporting both synchronous and asynchronous functions.
   - Automatically tracks latency, inputs, return values, errors, and step types.
   - Non-blocking asynchronous trace dispatch with local in-memory fallback buffering when the platform is offline.
2. **`ToolGatewayClient`:**
   - Proxies agent tool executions through the Tool Gateway MCP proxy.
   - Respects Guard decisions (`ALLOW`, `BLOCK`, `ASK_HUMAN`) and seamlessly executes registered local tool handlers on `ALLOW`.
3. **Decoupled Packaging:** Maintained in `sdk/` with its own `pyproject.toml` so external agent codebases can install it cleanly with minimal footprint.

## Consequences
- **Positive:** Developers can onboard an agent to Proofline in under 5 minutes by adding `@trace`.
- **Trade-off:** Advanced distributed tracing requires passing session IDs or setting context variables.
