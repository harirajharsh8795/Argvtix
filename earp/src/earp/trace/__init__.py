"""
EARP Trace Module — The CCTV System for AI Agents.

Records every step an AI agent takes:
- LLM calls (prompt, model, tokens, cost, latency)
- Retrieval steps (query, chunks, scores, method)
- Tool calls (tool name, arguments, result)
- Guard decisions (action, checks, decision)
- Approval steps (reviewer, decision, reason)
- Output (final response to user)
- Errors (exceptions, stack traces)
"""
