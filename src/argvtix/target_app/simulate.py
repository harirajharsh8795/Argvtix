"""
Simulation CLI — run the ShopOps AI agent against realistic tickets.

Usage:
    python -m argvtix.target_app.simulate
    python -m argvtix.target_app.simulate --ticket "Order 5 ka refund karo" --customer 1
    python -m argvtix.target_app.simulate --scenario all
    python -m argvtix.target_app.simulate --scenario refund_blocked
"""

from __future__ import annotations

import argparse
import textwrap
from typing import NamedTuple

from argvtix.db.session import SessionLocal, init_db
from argvtix.target_app.agent import ShopOpsAgent
from argvtix.target_app.llm import MockLLM

# ---------------------------------------------------------------------------
# Pre-built simulation scenarios
# ---------------------------------------------------------------------------


class Scenario(NamedTuple):
    name: str
    ticket: str
    customer_id: int
    description: str


SCENARIOS: list[Scenario] = [
    Scenario(
        name="refund_normal",
        ticket="Mujhe order 3 ka refund chahiye, item damage tha",
        customer_id=1,
        description="Normal refund request (low amount — should ALLOW)",
    ),
    Scenario(
        name="refund_large",
        ticket="Please process refund for my order 1 — it was defective",
        customer_id=1,
        description="Large amount refund (may trigger ASK_HUMAN if > Rs10,000)",
    ),
    Scenario(
        name="cancel_pending",
        ticket="Mera order 2 cancel karo abhi shipped nahi hua hai",
        customer_id=1,
        description="Cancel a pending order",
    ),
    Scenario(
        name="balance_inquiry",
        ticket="Mera wallet balance kitna hai?",
        customer_id=2,
        description="Read-only balance check — should always ALLOW",
    ),
    Scenario(
        name="wrong_customer",
        ticket="Order 1 ka refund chahiye",
        customer_id=999,
        description="Customer trying to refund an order that doesn't belong to them",
    ),
    Scenario(
        name="unknown_intent",
        ticket="Mujhe samajh nahi aa raha mera account mein kya ho raha hai",
        customer_id=1,
        description="Ambiguous ticket — agent should classify as unknown",
    ),
]


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------


def _divider(char: str = "-", width: int = 60) -> str:
    return char * width


def print_result(scenario: str, ticket: str, customer_id: int, result) -> None:
    print()
    print(_divider("="))
    print(f"  SCENARIO : {scenario}")
    print(f"  TICKET   : {ticket}")
    print(f"  CUSTOMER : #{customer_id}")
    print(_divider("-"))
    print(f"  Intent   : {result.intent}")
    print(f"  Guard    : {result.guard_decision}")
    print(f"  Status   : {result.state.get('status', 'unknown')}")
    print(f"  Trace ID : {result.trace.trace_id}")
    print(f"  Steps    : {len(result.trace.steps)}")
    print(f"  Duration : {result.trace.total_latency_ms:.1f} ms")
    print()
    print("  RESPONSE:")
    print(textwrap.indent(result.response, "    "))
    print(_divider("="))


def print_trace_detail(result) -> None:
    """Print each TraceStep in the trace."""
    print()
    print("  TRACE STEPS:")
    for step in result.trace.steps:
        node = step.metadata.get("node", "unknown") if step.metadata else "unknown"
        dur = f"{step.duration_ms:.1f}ms" if step.duration_ms is not None else "0ms"
        print(f"  [{step.step_index}] {step.step_type.value:18s} | {node:20s} | {dur}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ShopOps AI Agent Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python -m argvtix.target_app.simulate
          python -m argvtix.target_app.simulate --scenario refund_normal
          python -m argvtix.target_app.simulate --ticket "Order 5 refund" --customer 1
          python -m argvtix.target_app.simulate --scenario all --trace
        """),
    )
    parser.add_argument("--ticket", help="Custom ticket text to simulate")
    parser.add_argument("--customer", type=int, default=1, help="Customer ID (default: 1)")
    parser.add_argument(
        "--scenario",
        choices=[s.name for s in SCENARIOS] + ["all"],
        default="all",
        help="Pre-built scenario to run (default: all)",
    )
    parser.add_argument("--trace", action="store_true", help="Print full trace step detail")
    parser.add_argument(
        "--mock", action="store_true", default=True, help="Use MockLLM (default, no API key needed)"
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    llm = MockLLM() if args.mock else None
    agent = ShopOpsAgent(db=db, llm=llm)

    print()
    print("  +----------------------------------------------+")
    print("  |       ARGVTIX - ShopOps Agent Simulator         |")
    print("  |        (LangGraph + ARGVTIX Trace Engine)       |")
    print("  +----------------------------------------------+")

    try:
        if args.ticket:
            # Custom single ticket
            result = agent.run(ticket_text=args.ticket, customer_id=args.customer)
            print_result("custom", args.ticket, args.customer, result)
            if args.trace:
                print_trace_detail(result)

        elif args.scenario == "all":
            for s in SCENARIOS:
                result = agent.run(ticket_text=s.ticket, customer_id=s.customer_id)
                print_result(s.name, s.ticket, s.customer_id, result)
                if args.trace:
                    print_trace_detail(result)

        else:
            s = next(sc for sc in SCENARIOS if sc.name == args.scenario)
            result = agent.run(ticket_text=s.ticket, customer_id=s.customer_id)
            print_result(s.name, s.ticket, s.customer_id, result)
            if args.trace:
                print_trace_detail(result)

    finally:
        db.close()

    print()
    print("  Simulation complete. All traces recorded.")
    print()


if __name__ == "__main__":
    main()
