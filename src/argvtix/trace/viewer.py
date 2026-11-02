"""
Trace Viewer CLI — Visual inspection of recorded AI traces in the terminal.

Usage:
    python -m argvtix.trace.viewer --latest
    python -m argvtix.trace.viewer tr-a1b2c3d4e5f6
    python -m argvtix.trace.viewer --list
"""
from __future__ import annotations

import argparse
import sys
import textwrap

from argvtix.db.session import SessionLocal, init_db
from argvtix.trace.schemas import StepType, Trace
from argvtix.trace.store import get_trace, list_trace_records


def _divider(char: str = "-", width: int = 65) -> str:
    return char * width


def format_step_detail(step) -> str:
    """Format single step details based on its step_type."""
    node = step.metadata.get("node", "unknown") if step.metadata else "unknown"
    dur = f"{step.duration_ms:.1f}ms" if step.duration_ms is not None else "0.0ms"

    lines = [f"  [{step.step_index}] {step.step_type.value:16s} | {node:18s} | {dur:>8s}"]

    if step.step_type == StepType.LLM_CALL and step.llm_call:
        c = step.llm_call
        lines.append(f"       Model: {c.model} | Tokens: {c.total_tokens} (in: {c.input_tokens}, out: {c.output_tokens})")
        if c.output_text:
            snippet = c.output_text.replace("\n", " ")[:70]
            lines.append(f"       Output snippet: {snippet}...")

    elif step.step_type == StepType.RETRIEVAL and step.retrieval:
        r = step.retrieval
        lines.append(f"       Query: {r.query[:60]} | Chunks: {r.num_results} | Method: {r.method}")

    elif step.step_type == StepType.GUARD_DECISION and step.guard_decision:
        g = step.guard_decision
        dec_str = g.decision.value if hasattr(g.decision, "value") else str(g.decision)
        lines.append(f"       Action: {g.action} | Decision: {dec_str.upper()}")
        if g.reasons:
            lines.append(f"       Reason: {g.reasons[0][:70]}")

    elif step.step_type == StepType.TOOL_CALL and step.tool_call:
        t = step.tool_call
        status_str = "SUCCESS" if t.is_success else "FAILED"
        lines.append(f"       Tool: {t.tool_name} [{status_str}] | Args: {t.tool_args}")

    elif step.step_type == StepType.OUTPUT and step.output:
        lines.append(f"       Response: {step.output.response_text[:75]}...")

    elif step.step_type == StepType.ERROR and step.error:
        lines.append(f"       Error: [{step.error.error_type}] {step.error.error_message}")

    return "\n".join(lines)


def display_trace(trace: Trace) -> None:
    """Print a formatted visual view of a full trace."""
    status_str = trace.status.value.upper()
    print()
    print(_divider("="))
    print(f"  TRACE DETAILS : {trace.trace_id}")
    print(_divider("-"))
    print(f"  Status        : {status_str}")
    print(f"  Customer ID   : #{trace.customer_id or 'N/A'}")
    print(f"  Session ID    : {trace.session_id or 'N/A'}")
    print(f"  Total Latency : {trace.total_latency_ms:.1f} ms")
    print(f"  Total Tokens  : {trace.total_tokens}")
    print(f"  Total Cost    : ${trace.total_cost_usd:.4f}")
    print(f"  Steps Count   : {len(trace.steps)}")
    print(_divider("-"))
    print("  INPUT TICKET:")
    print(textwrap.indent(trace.input_text, "    "))
    print(_divider("-"))
    print("  EXECUTION TIMELINE:")
    for step in trace.steps:
        print(format_step_detail(step))
    print(_divider("="))
    print()


def display_recent_traces(records) -> None:
    """Print a list of recent traces."""
    print()
    print("  +---------------------------------------------------------------+")
    print("  |                     RECENT RECORDED TRACES                    |")
    print("  +---------------------------------------------------------------+")
    print(f"  {'Trace ID':<20} | {'Status':<10} | {'Latency':<9} | {'Tokens':<7} | {'Workflow':<12}")
    print(_divider("-"))

    if not records:
        print("  No traces found in database. Run simulate or test to generate traces.")
        print(_divider("-"))
        return

    for r in records:
        status_val = r.status.upper() if r.status else "UNKNOWN"
        wf = r.workflow_type or "general"
        lat = f"{r.total_latency_ms:.0f}ms" if r.total_latency_ms is not None else "0ms"
        tokens = str(r.total_tokens or 0)
        print(f"  {r.id:<20} | {status_val:<10} | {lat:<9} | {tokens:<7} | {wf:<12}")

    print(_divider("-"))
    print("  Tip: View any trace with: python -m argvtix.trace.viewer <trace_id>")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="ARGVTIX Trace Viewer CLI")
    parser.add_argument("trace_id", nargs="?", help="Trace ID to inspect (e.g. tr-abc123)")
    parser.add_argument("--latest", action="store_true", help="View the most recent trace")
    parser.add_argument("--list", action="store_true", help="List recent recorded traces")
    parser.add_argument("--limit", type=int, default=10, help="Number of traces to list (default: 10)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        if args.trace_id:
            trace = get_trace(db, args.trace_id)
            if not trace:
                print(f"Trace not found: {args.trace_id}")
                sys.exit(1)
            display_trace(trace)

        elif args.latest:
            records = list_trace_records(db, limit=1)
            if not records:
                print("No traces found in database.")
                sys.exit(0)
            trace = get_trace(db, records[0].id)
            if trace:
                display_trace(trace)

        else:
            records = list_trace_records(db, limit=args.limit)
            display_recent_traces(records)

    finally:
        db.close()


if __name__ == "__main__":
    main()
