"""
ShopOps AI Agent — powered by LangGraph.

Architecture:
  [START]
     │
     ▼
  classify_intent          ← LLM: extract intent, order_id, amount from ticket
     │
     ▼
  retrieve_policy          ← RAG: fetch relevant SOP chunks
     │
     ▼
  check_guard              ← Guard Engine: ALLOW / BLOCK / ASK_HUMAN
     │
  ┌──┴────────────────────────────┐
  │ ALLOW        │ ASK_HUMAN      │ BLOCK
  ▼              ▼                ▼
execute_tool  route_approval   generate_response("denied")
  │              │
  ▼              ▼
generate_response  generate_response("pending approval")
  │
  ▼
 [END]
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from argvtix.guard.engine import ActionGuard, GuardCheckRequest
from argvtix.security.dlp import DLPFilter
from argvtix.security.pii import PIIMasker
from argvtix.target_app.llm import LLMProtocol, get_default_llm
from argvtix.target_app.rag.retriever import retrieve_policy
from argvtix.target_app.tools.shop_tools import (
    cancel_order,
    check_inventory,
    get_customer_balance,
    get_order,
    issue_refund,
)
from argvtix.trace.recorder import TraceRecorder
from argvtix.trace.schemas import Trace

# ---------------------------------------------------------------------------
# Agent State (passed between LangGraph nodes)
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    # Inputs
    ticket_text: str
    customer_id: int | None
    session_id: str

    # Extracted by classify_intent
    intent: str                  # refund | cancel_order | balance_inquiry | inventory_check | unknown
    order_id: int | None
    amount: float | None
    confidence: float

    # Retrieved by retrieve_policy
    policy_chunks: list[str]

    # Set by check_guard
    guard_decision: str          # ALLOW | BLOCK | ASK_HUMAN
    guard_reason: str
    guard_policy: str | None

    # Set by execute_tool
    tool_name: str | None
    tool_result: dict | None
    tool_success: bool

    # Set by generate_response
    final_response: str
    status: str                  # completed | blocked | pending_approval | error

    # Error handling
    error: str | None


# ---------------------------------------------------------------------------
# Node: classify_intent
# ---------------------------------------------------------------------------

def make_classify_node(llm: LLMProtocol, recorder: TraceRecorder):
    def classify_intent(state: AgentState) -> AgentState:
        ticket = state.get("ticket_text", "")

        prompt = (
            "You are an intent classifier for a customer support system.\n"
            "Classify the following customer ticket into one of these intents:\n"
            "  refund, cancel_order, balance_inquiry, inventory_check, unknown\n\n"
            f"Customer ticket: {ticket}\n\n"
            "Return ONLY a valid JSON object with keys: intent, order_id, amount, confidence.\n"
            "order_id and amount can be null if not mentioned.\n"
            "Example: {\"intent\": \"refund\", \"order_id\": 42, \"amount\": null, \"confidence\": 0.95}"
        )

        t0 = time.monotonic()
        raw = llm.call(prompt)
        latency = (time.monotonic() - t0) * 1000

        recorder.record_llm_call(
            node="classify_intent",
            model="gemini-2.0-flash",
            prompt=prompt,
            response=raw,
            latency_ms=latency,
        )

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"intent": "unknown", "order_id": None, "amount": None, "confidence": 0.0}

        return {
            **state,
            "intent": parsed.get("intent", "unknown"),
            "order_id": parsed.get("order_id"),
            "amount": parsed.get("amount"),
            "confidence": parsed.get("confidence", 0.0),
        }

    return classify_intent


# ---------------------------------------------------------------------------
# Node: retrieve_policy
# ---------------------------------------------------------------------------

def make_retrieve_node(recorder: TraceRecorder):
    def retrieve_policy_node(state: AgentState) -> AgentState:
        query = f"{state.get('intent', '')} {state.get('ticket_text', '')}"

        t0 = time.monotonic()
        chunks = retrieve_policy(query, top_k=3)
        latency = (time.monotonic() - t0) * 1000

        recorder.record_retrieval(
            node="retrieve_policy",
            query=query,
            retrieved_chunks=chunks,
            latency_ms=latency,
        )

        return {**state, "policy_chunks": chunks}

    return retrieve_policy_node


# ---------------------------------------------------------------------------
# Node: check_guard
# ---------------------------------------------------------------------------

def make_guard_node(db: Session, recorder: TraceRecorder):
    guard = ActionGuard()
    read_only_intents = {"balance_inquiry", "inventory_check", "unknown"}

    def check_guard(state: AgentState) -> AgentState:
        intent = state.get("intent", "unknown")
        customer_id = state.get("customer_id")
        order_id = state.get("order_id")
        amount = state.get("amount") or 0.0

        t0 = time.monotonic()

        # Read-only intents skip guard evaluation — always ALLOW
        if intent in read_only_intents:
            latency = (time.monotonic() - t0) * 1000
            recorder.record_guard_decision(
                node="check_guard",
                action_type=intent,
                action_params={"customer_id": customer_id},
                decision="ALLOW",
                reason="Read-only operation — no guard check needed.",
                latency_ms=latency,
                policy_triggered=None,
            )
            return {**state, "guard_decision": "ALLOW", "guard_reason": "Read-only", "guard_policy": None}

        # Build GuardCheckRequest for write operations
        req = GuardCheckRequest(
            workflow_type=intent,
            tool_name=intent,
            customer_id=str(customer_id or ""),
            order_id=str(order_id or ""),
            amount=float(amount),
            reason="agent_initiated",
        )
        response = guard.evaluate(req, db)
        latency = (time.monotonic() - t0) * 1000

        # Normalise decision to string
        decision_str = (
            response.decision.value
            if hasattr(response.decision, "value")
            else str(response.decision)
        )

        recorder.record_guard_decision(
            node="check_guard",
            action_type=intent,
            action_params={"customer_id": customer_id, "order_id": order_id, "amount": amount},
            decision=decision_str,
            reason=response.reason,
            latency_ms=latency,
            policy_triggered=response.policy_rule_triggered,
        )

        return {
            **state,
            "guard_decision": decision_str,
            "guard_reason": response.reason,
            "guard_policy": response.policy_rule_triggered,
        }

    return check_guard


# ---------------------------------------------------------------------------
# Node: execute_tool
# ---------------------------------------------------------------------------

def make_execute_node(db: Session, recorder: TraceRecorder):
    def execute_tool(state: AgentState) -> AgentState:
        intent = state.get("intent")
        customer_id = state.get("customer_id")
        order_id = state.get("order_id")
        amount = state.get("amount")

        tool_name = None
        tool_inputs: dict[str, Any] = {}
        result = None

        t0 = time.monotonic()

        if intent == "refund" and order_id:
            tool_name = "issue_refund"
            tool_inputs = {"customer_id": customer_id, "order_id": order_id, "amount": amount or 0}
            result = issue_refund(db, customer_id=customer_id, order_id=order_id, amount=amount or 0)

        elif intent == "cancel_order" and order_id:
            tool_name = "cancel_order"
            tool_inputs = {"customer_id": customer_id, "order_id": order_id}
            result = cancel_order(db, customer_id=customer_id, order_id=order_id)

        elif intent == "balance_inquiry":
            tool_name = "get_customer_balance"
            tool_inputs = {"customer_id": customer_id}
            result = get_customer_balance(db, customer_id=customer_id)

        elif intent == "inventory_check":
            tool_name = "check_inventory"
            tool_inputs = {"product_id": order_id or 1}
            result = check_inventory(db, product_id=order_id or 1)

        else:
            tool_name = "get_order"
            tool_inputs = {"order_id": order_id or 0}
            result = get_order(db, order_id=order_id or 0) if order_id else None

        latency = (time.monotonic() - t0) * 1000

        if result:
            recorder.record_tool_call(
                node="execute_tool",
                tool_name=tool_name or "noop",
                inputs=tool_inputs,
                outputs=result.data,
                latency_ms=latency,
                success=result.success,
                error=result.error,
            )
            return {
                **state,
                "tool_name": tool_name,
                "tool_result": result.data,
                "tool_success": result.success,
                "error": result.error,
            }

        return {**state, "tool_name": None, "tool_result": {}, "tool_success": False}

    return execute_tool


# ---------------------------------------------------------------------------
# Node: generate_response
# ---------------------------------------------------------------------------

def make_response_node(llm: LLMProtocol, recorder: TraceRecorder):
    def generate_response(state: AgentState) -> AgentState:
        guard_decision = state.get("guard_decision", "ALLOW")
        tool_result = state.get("tool_result", {})
        intent = state.get("intent", "unknown")
        reason = state.get("guard_reason", "")

        context = (
            f"Customer intent: {intent}\n"
            f"Guard decision: {guard_decision}\n"
            f"Guard reason: {reason}\n"
            f"Tool result: {json.dumps(tool_result)}\n"
        )

        prompt = (
            "You are a helpful customer support AI agent for ShopOps.\n"
            "Generate a friendly, concise response in Hinglish (Hindi + English mix) "
            "for the customer based on the context below.\n"
            "Keep the response under 3 sentences.\n\n"
            f"Context:\n{context}\n\n"
            "Response:"
        )

        t0 = time.monotonic()
        response_text = llm.call(prompt)
        latency = (time.monotonic() - t0) * 1000

        recorder.record_llm_call(
            node="generate_response",
            model="gemini-2.0-flash",
            prompt=prompt,
            response=response_text,
            latency_ms=latency,
        )
        recorder.record_output(
            node="generate_response",
            response_text=response_text,
            latency_ms=0,
        )

        # Determine final status
        if guard_decision == "BLOCK":
            final_status = "blocked"
        elif guard_decision == "ASK_HUMAN":
            final_status = "pending_approval"
        else:
            final_status = "completed"

        return {
            **state,
            "final_response": response_text,
            "status": final_status,
        }

    return generate_response


# ---------------------------------------------------------------------------
# Router — decides which edge to take after check_guard
# ---------------------------------------------------------------------------

def route_after_guard(state: AgentState) -> str:
    decision = str(state.get("guard_decision", "allow")).lower()
    if decision in ("allow", "guarddecision.allow"):
        return "execute_tool"
    # Both BLOCK and ASK_HUMAN go directly to generate_response
    return "generate_response"


# ---------------------------------------------------------------------------
# ShopOpsAgent — assembles and runs the LangGraph
# ---------------------------------------------------------------------------

class ShopOpsAgent:
    """
    Orchestrates the ShopOps customer support workflow.

    Usage:
        agent = ShopOpsAgent(db=session)
        result = agent.run(
            ticket_text="Order 42 ka refund chahiye",
            customer_id=1,
        )
        print(result.trace.trace_id, result.response)
    """

    def __init__(
        self,
        db: Session,
        llm: LLMProtocol | None = None,
        workflow_id: str = "wf-shopops-support",
    ) -> None:
        self._db = db
        self._llm = llm or get_default_llm()
        self._workflow_id = workflow_id
        self._pii_masker = PIIMasker()
        self._dlp = DLPFilter(pii_masker=self._pii_masker)

    def run(
        self,
        ticket_text: str,
        customer_id: int | None = None,
        session_id: str | None = None,
    ) -> AgentRunResult:
        sid = session_id or f"sess-{uuid.uuid4().hex[:8]}"

        # Step 1: Inbound PII Sanitization (Aadhaar, Phone, Email, PAN, Card, UPI)
        mask_res = self._pii_masker.mask(ticket_text)
        sanitized_input = mask_res.masked_text

        recorder = TraceRecorder(
            input_text=sanitized_input,
            session_id=sid,
            workflow_id=self._workflow_id,
            customer_id=customer_id,
        )

        # Build a fresh graph with closures that capture this run's recorder
        graph = _build_graph(
            db=self._db,
            llm=self._llm,
            recorder=recorder,
        )

        initial_state: AgentState = {
            "ticket_text": sanitized_input,
            "customer_id": customer_id,
            "session_id": sid,
            "policy_chunks": [],
            "guard_decision": "ALLOW",
            "guard_reason": "",
            "tool_success": False,
            "status": "completed",
        }

        try:
            final_state = graph.invoke(initial_state)
            status = final_state.get("status", "completed")
        except Exception as exc:
            recorder.record_error(
                node="agent_run",
                error_type=type(exc).__name__,
                message=str(exc),
            )
            final_state = {**initial_state, "final_response": "Kuch technical issue aayi. Please thodi der baad try karein.", "status": "failed"}
            status = "failed"

        # Step 2: Outbound DLP filter (checks for leaked system prompt, stack traces, unmasked PII)
        raw_response = final_state.get("final_response", "")
        safe_response = self._dlp.sanitize(raw_response)

        # Map to valid TraceStatus values
        trace_status = "blocked" if status == "blocked" else ("failed" if status in ("error", "failed") else "completed")
        trace = recorder.build_trace(status=trace_status)

        return AgentRunResult(
            response=safe_response,
            guard_decision=final_state.get("guard_decision", "ALLOW"),
            intent=final_state.get("intent", "unknown"),
            trace=trace,
            state=final_state,
        )


def _build_graph(
    db: Session,
    llm: LLMProtocol,
    recorder: TraceRecorder,
) -> StateGraph:
    """Wire up all nodes and edges into a LangGraph StateGraph."""
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("classify_intent", make_classify_node(llm, recorder))
    graph.add_node("retrieve_policy", make_retrieve_node(recorder))
    graph.add_node("check_guard", make_guard_node(db, recorder))
    graph.add_node("execute_tool", make_execute_node(db, recorder))
    graph.add_node("generate_response", make_response_node(llm, recorder))

    # Edges
    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "retrieve_policy")
    graph.add_edge("retrieve_policy", "check_guard")
    graph.add_conditional_edges("check_guard", route_after_guard)
    graph.add_edge("execute_tool", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class AgentRunResult:
    """Returned by ShopOpsAgent.run()."""

    def __init__(
        self,
        response: str,
        guard_decision: str,
        intent: str,
        trace: Trace,
        state: AgentState,
    ) -> None:
        self.response = response
        self.guard_decision = guard_decision
        self.intent = intent
        self.trace = trace
        self.state = state

    def __repr__(self) -> str:
        return (
            f"AgentRunResult("
            f"intent={self.intent!r}, "
            f"guard={self.guard_decision!r}, "
            f"trace_id={self.trace.trace_id!r})"
        )
