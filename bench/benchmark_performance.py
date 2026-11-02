"""
Performance & Scalability Benchmark Suite for ARGVTIX
Measures database query latencies, query counts, and API response metrics
with realistic datasets before and after optimization.
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, create_engine, event, func
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import (
    Base,
    Customer,
    InventoryLog,
    LedgerEntry,
    Order,
    OrderItem,
    Payment,
    Product,
    Refund,
    TraceRecord,
    TraceStepRecord,
    WatchdogFindingRecord,
)
from argvtix.guard import ActionGuard, GuardCheckRequest
from argvtix.watchdog.engine import WatchdogEngine


class QueryCounter:
    """SQLAlchemy query listener counting statement executions during a block."""

    def __init__(self, engine):
        self.engine = engine
        self.count = 0
        self.queries: list[str] = []

    def __enter__(self):
        self.count = 0
        self.queries = []
        event.listen(self.engine, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        event.remove(self.engine, "before_cursor_execute", self._callback)

    def _callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.queries.append(statement)


def seed_benchmark_data(
    session: Session,
    num_customers: int = 200,
    num_orders: int = 800,
    num_traces: int = 1000,
    seed: int = 42,
) -> None:
    """Populate database with synthetic data for realistic benchmarking."""
    rng = random.Random(seed)

    # 1. Products
    products = []
    for i in range(50):
        p = Product(
            id=f"prod_bench_{i}",
            sku=f"SKU-BENCH-{i:04d}",
            title=f"Benchmark Product {i}",
            price=round(rng.uniform(100.0, 5000.0), 2),
            inventory_count=rng.randint(50, 500),
            category=rng.choice(["electronics", "apparel", "home", "books"]),
        )
        products.append(p)
    session.add_all(products)
    session.flush()

    # 2. Customers
    customers = []
    for i in range(num_customers):
        c = Customer(
            id=f"cust_bench_{i}",
            name=f"Customer {i}",
            email=f"customer_{i}@example.com",
            phone=f"+9198765{i:05d}",
            wallet_balance=round(rng.uniform(0.0, 10000.0), 2),
            tier=rng.choice(["standard", "silver", "gold", "platinum"]),
        )
        customers.append(c)
    session.add_all(customers)
    session.flush()

    # 3. Orders, Items, Payments, Refunds
    orders = []
    items = []
    payments = []
    refunds = []
    inventory_logs = []

    for i in range(num_orders):
        cust = rng.choice(customers)
        status = rng.choice(["completed", "completed", "completed", "pending", "cancelled", "refunded"])
        subtotal = 0.0
        order_id = f"ord_bench_{i}"

        # Items
        item_count = rng.randint(1, 4)
        for j in range(item_count):
            prod = rng.choice(products)
            qty = rng.randint(1, 3)
            lt = round(prod.price * qty, 2)
            subtotal += lt
            items.append(
                OrderItem(
                    id=f"item_bench_{i}_{j}",
                    order_id=order_id,
                    product_id=prod.id,
                    quantity=qty,
                    unit_price=prod.price,
                    line_total=lt,
                )
            )
            # Add inventory log for some completed orders
            if status == "completed" and rng.random() > 0.05:
                inventory_logs.append(
                    InventoryLog(
                        id=f"inv_bench_{i}_{j}",
                        product_id=prod.id,
                        order_id=order_id,
                        change_amount=-qty,
                        reason="order_placed",
                    )
                )

        tax = round(subtotal * 0.18, 2)
        total = round(subtotal + tax, 2)

        # Plant deliberate 2% mismatch for testing watchdog
        if rng.random() < 0.02:
            total += 10.0

        ord_obj = Order(
            id=order_id,
            customer_id=cust.id,
            status=status,
            subtotal=round(subtotal, 2),
            tax=tax,
            total_amount=total,
            created_at=datetime.now(UTC) - timedelta(hours=rng.randint(1, 720)),
        )
        orders.append(ord_obj)

        # Payment
        if status in ("completed", "refunded"):
            pmt = Payment(
                id=f"pmt_bench_{i}",
                order_id=order_id,
                customer_id=cust.id,
                amount=total,
                status="succeeded",
                method=rng.choice(["upi", "credit_card", "netbanking"]),
                created_at=ord_obj.created_at,
            )
            payments.append(pmt)

            # Some orders have refunds
            if status == "refunded" or rng.random() < 0.15:
                ref_amt = total if status == "refunded" else round(rng.uniform(50.0, total), 2)
                refunds.append(
                    Refund(
                        id=f"ref_bench_{i}",
                        order_id=order_id,
                        payment_id=pmt.id,
                        customer_id=cust.id,
                        amount=ref_amt,
                        status="completed",
                        reason="Customer return request",
                        created_at=ord_obj.created_at + timedelta(hours=1),
                    )
                )

    session.add_all(orders)
    session.add_all(items)
    session.add_all(payments)
    session.add_all(refunds)
    session.add_all(inventory_logs)
    session.flush()

    # 4. Ledger entries
    ledger_entries = []
    for c in customers:
        entry_count = rng.randint(2, 8)
        for k in range(entry_count):
            etype = "credit" if k == 0 or rng.random() > 0.4 else "debit"
            amt = round(rng.uniform(100.0, 2000.0), 2)
            ledger_entries.append(
                LedgerEntry(
                    id=f"ledg_{c.id}_{k}",
                    customer_id=c.id,
                    entry_type=etype,
                    amount=amt,
                    description=f"Synthetic transaction {k}",
                    created_at=datetime.now(UTC) - timedelta(days=rng.randint(1, 30)),
                )
            )
    session.add_all(ledger_entries)

    # 5. Traces
    traces = []
    steps = []
    for t_idx in range(num_traces):
        trace_id = f"tr_bench_{t_idx:05d}"
        wf = rng.choice(["refund", "order_status", "cancel_order", "address_change"])
        stat = rng.choice(["completed", "completed", "completed", "error", "blocked"])
        tot_lat = round(rng.uniform(150.0, 1800.0), 2)
        tot_cost = round(rng.uniform(0.001, 0.04), 4)
        tokens = rng.randint(300, 2500)

        tr = TraceRecord(
            id=trace_id,
            project_id="default",
            session_id=f"sess_{t_idx % 50}",
            user_id=f"user_{t_idx % 100}",
            channel="web",
            workflow_type=wf,
            status=stat,
            input_text=f"Benchmark input query {t_idx} regarding order {t_idx % 100}",
            output_text=f"Processed response for benchmark query {t_idx}",
            total_latency_ms=tot_lat,
            total_cost_usd=tot_cost,
            total_tokens=tokens,
            tags_json=json.dumps([wf, stat]),
            metadata_json=json.dumps({"channel": "web", "workflow_type": wf}),
            created_at=datetime.now(UTC) - timedelta(minutes=rng.randint(1, 14400)),
        )
        traces.append(tr)

        # Trace Steps
        for s_idx in range(3):
            steps.append(
                TraceStepRecord(
                    id=f"step_{trace_id}_{s_idx}",
                    trace_id=trace_id,
                    step_index=s_idx,
                    step_type=rng.choice(["llm_call", "tool_call", "guard_check"]),
                    latency_ms=round(tot_lat / 3, 2),
                    step_data_json=json.dumps({"step": s_idx}),
                    created_at=tr.created_at,
                )
            )

    session.add_all(traces)
    session.add_all(steps)

    # 6. Watchdog findings
    findings = []
    for f_idx in range(150):
        findings.append(
            WatchdogFindingRecord(
                id=f"find_bench_{f_idx}",
                project_id="default",
                rule_name=rng.choice(["duplicate_refund", "order_total_mismatch", "ledger_balance_mismatch"]),
                severity=rng.choice(["critical", "high", "medium", "low"]),
                description=f"Benchmark finding {f_idx}",
                entity_type=rng.choice(["order", "customer"]),
                entity_id=f"ord_bench_{f_idx % 200}",
                details_json=json.dumps({"discrepancy": 15.0}),
                resolved=rng.choice([True, False, False]),
                detected_at=datetime.now(UTC) - timedelta(hours=rng.randint(1, 100)),
            )
        )
    session.add_all(findings)

    session.commit()


def run_benchmark_suite(db_engine, iterations: int = 5) -> dict[str, Any]:
    """Execute standard workload benchmarks and record timing metrics."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()

    metrics: dict[str, Any] = {}

    # Benchmark 1: Watchdog Engine Scan
    engine_inst = WatchdogEngine()
    watchdog_latencies = []
    watchdog_query_counts = []

    for _ in range(iterations):
        with QueryCounter(db_engine) as qc:
            t0 = time.perf_counter()
            findings = engine_inst.scan(session, persist=False)
            t1 = time.perf_counter()
            watchdog_latencies.append((t1 - t0) * 1000.0)
            watchdog_query_counts.append(qc.count)

    metrics["watchdog_scan"] = {
        "avg_latency_ms": round(sum(watchdog_latencies) / len(watchdog_latencies), 2),
        "min_latency_ms": round(min(watchdog_latencies), 2),
        "max_latency_ms": round(max(watchdog_latencies), 2),
        "queries_executed": watchdog_query_counts[0],
        "findings_detected": len(findings),
    }

    # Benchmark 2: Trace Stats Aggregation (Optimized Single Query)
    stats_latencies = []
    stats_query_counts = []
    for _ in range(iterations):
        with QueryCounter(db_engine) as qc:
            t0 = time.perf_counter()
            row = (
                session.query(
                    func.count(TraceRecord.id).label("total_traces"),
                    func.sum(
                        case((TraceRecord.status == "completed", 1), else_=0)
                    ).label("successful"),
                    func.avg(TraceRecord.total_latency_ms).label("avg_latency"),
                    func.sum(TraceRecord.total_cost_usd).label("total_cost"),
                    func.sum(TraceRecord.total_tokens).label("total_tokens"),
                )
                .first()
            )
            t1 = time.perf_counter()
            stats_latencies.append((t1 - t0) * 1000.0)
            stats_query_counts.append(qc.count)


    metrics["trace_stats"] = {
        "avg_latency_ms": round(sum(stats_latencies) / len(stats_latencies), 2),
        "queries_executed": stats_query_counts[0],
    }

    # Benchmark 3: Filtered Trace Listing
    list_latencies = []
    list_query_counts = []
    for _ in range(iterations):
        with QueryCounter(db_engine) as qc:
            t0 = time.perf_counter()
            query = session.query(TraceRecord).filter(
                TraceRecord.workflow_type == "refund",
                TraceRecord.status == "completed",
            )
            count = query.count()
            records = query.order_by(TraceRecord.created_at.desc()).limit(50).all()
            t1 = time.perf_counter()
            list_latencies.append((t1 - t0) * 1000.0)
            list_query_counts.append(qc.count)

    metrics["trace_filter_list"] = {
        "avg_latency_ms": round(sum(list_latencies) / len(list_latencies), 2),
        "queries_executed": list_query_counts[0],
        "result_count": len(records),
        "total_matches": count,
    }

    # Benchmark 4: Action Guard Pre-Execution Evaluation
    guard = ActionGuard()
    guard_latencies = []
    guard_query_counts = []
    sample_order = session.query(Order).first()
    if sample_order:
        req = GuardCheckRequest(
            workflow_type="refund",
            tool_name="issue_refund",
            customer_id=sample_order.customer_id,
            order_id=sample_order.id,
            amount=500.0,
            reason="Customer requested exchange",
        )
        for _ in range(iterations):
            with QueryCounter(db_engine) as qc:
                t0 = time.perf_counter()
                resp = guard.evaluate(req, session)
                t1 = time.perf_counter()
                guard_latencies.append((t1 - t0) * 1000.0)
                guard_query_counts.append(qc.count)

        metrics["guard_evaluate"] = {
            "avg_latency_ms": round(sum(guard_latencies) / len(guard_latencies), 2),
            "queries_executed": guard_query_counts[0],
            "decision": resp.decision.value,
        }

    # Benchmark 5: Watchdog Findings Unresolved Filter
    finding_latencies = []
    finding_query_counts = []
    for _ in range(iterations):
        with QueryCounter(db_engine) as qc:
            t0 = time.perf_counter()
            q = session.query(WatchdogFindingRecord).filter(
                WatchdogFindingRecord.resolved == False,
                WatchdogFindingRecord.severity == "high",
            )
            f_count = q.count()
            f_records = q.order_by(WatchdogFindingRecord.detected_at.desc()).limit(50).all()
            t1 = time.perf_counter()
            finding_latencies.append((t1 - t0) * 1000.0)
            finding_query_counts.append(qc.count)

    metrics["watchdog_findings_filter"] = {
        "avg_latency_ms": round(sum(finding_latencies) / len(finding_latencies), 2),
        "queries_executed": finding_query_counts[0],
        "result_count": len(f_records),
    }

    session.close()
    return metrics


def main():
    print("=== ARGVTIX Performance & Database Query Benchmark ===")
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)

    print("1. Seeding synthetic dataset (200 customers, 800 orders, 1,000 traces, etc.)...")
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    seed_benchmark_data(session)
    session.close()

    print("2. Running benchmark suite...")
    results = run_benchmark_suite(test_engine, iterations=5)

    print("\n=== Benchmark Results ===")
    print(json.dumps(results, indent=2))

    # Save to bench/baseline_results.json
    out_path = os.path.join(os.path.dirname(__file__), "baseline_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nBaseline metrics saved to: {out_path}")


if __name__ == "__main__":
    main()
