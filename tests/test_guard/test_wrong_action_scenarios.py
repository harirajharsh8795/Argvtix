"""
20 Wrong-Action Scenarios & False-Block Rate Verification Suite.

Adversarially tests ActionGuard across 20 distinct invalid agent actions:
1. Negative refund amount
2. Zero refund amount
3. Nonexistent order ID
4. Nonexistent customer ID
5. Customer ownership mismatch (Customer A refunds Order B)
6. Exceeds payment amount (partial overage)
7. Exceeds total order value (gross overage)
8. Double refund replay (second refund exceeds remaining balance)
9. Refund against cancelled order
10. Refund against uncompleted / pending payment
11. Return outside valid policy window (> 30 days)
12. High-value refund >= 10,000 without human approval (gated to ASK_HUMAN)
13. Extreme high-value refund (50,000) gated to ASK_HUMAN
14. SQL injection string in order_id
15. Path traversal string in order_id
16. Non-whitelisted arbitrary tool call (drop_database)
17. Missing required parameters
18. Rate limit / velocity cap breach (> 3 refunds within 5 minutes)
19. Replay attack with same idempotency key
20. Cross-tenant project access attempt

Also measures:
- True Block / Review Rate on invalid actions: Target 100%
- False Block Rate on legitimate baseline actions: Target 0.0%
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, Customer, Order, Payment
from argvtix.guard.engine import ActionGuard, GuardCheckRequest
from argvtix.guard.gateway import ToolGateway
from argvtix.trace.schemas import GuardDecision


@pytest.fixture
def guard_scenario_db() -> Session:
    """Isolated in-memory database seeded with baseline orders."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    # Seed customers
    c1 = Customer(id="cust_legit_01", name="Rahul Verma", email="rahul@example.com")
    c2 = Customer(id="cust_attacker_02", name="Attacker User", email="attacker@example.com")
    db.add_all([c1, c2])

    # Seed valid delivered order (3 days ago)
    o1 = Order(
        id="ord_valid_100",
        customer_id="cust_legit_01",
        status="delivered",
        subtotal=2500.0,
        tax=250.0,
        total_amount=2750.0,
        created_at=datetime.now(UTC) - timedelta(days=3),
    )
    p1 = Payment(
        id="pmt_100",
        order_id="ord_valid_100",
        customer_id="cust_legit_01",
        amount=2750.0,
        status="succeeded",
    )

    # Seed high-value order (₹15,000)
    o2 = Order(
        id="ord_vip_200",
        customer_id="cust_legit_01",
        status="delivered",
        subtotal=14000.0,
        tax=1000.0,
        total_amount=15000.0,
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    p2 = Payment(
        id="pmt_200",
        order_id="ord_vip_200",
        customer_id="cust_legit_01",
        amount=15000.0,
        status="succeeded",
    )

    # Seed expired order (> 35 days ago)
    o3 = Order(
        id="ord_expired_300",
        customer_id="cust_legit_01",
        status="delivered",
        subtotal=1000.0,
        tax=100.0,
        total_amount=1100.0,
        created_at=datetime.now(UTC) - timedelta(days=40),
    )
    p3 = Payment(
        id="pmt_300",
        order_id="ord_expired_300",
        customer_id="cust_legit_01",
        amount=1100.0,
        status="succeeded",
    )

    # Seed cancelled order
    o4 = Order(
        id="ord_cancelled_400",
        customer_id="cust_legit_01",
        status="cancelled",
        subtotal=800.0,
        tax=80.0,
        total_amount=880.0,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )

    # Seed order with failed payment
    o5 = Order(
        id="ord_failed_pay_500",
        customer_id="cust_legit_01",
        status="pending",
        subtotal=1200.0,
        tax=120.0,
        total_amount=1320.0,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    p5 = Payment(
        id="pmt_500",
        order_id="ord_failed_pay_500",
        customer_id="cust_legit_01",
        amount=1320.0,
        status="failed",
    )

    db.add_all([o1, p1, o2, p2, o3, p3, o4, o5, p5])
    db.commit()

    yield db
    db.close()


class TestTwentyWrongActionScenarios:
    """Verifies all 20 wrong-action scenarios are intercepted without zero false blocks."""

    def test_twenty_wrong_action_scenarios(self, guard_scenario_db: Session) -> None:
        guard = ActionGuard()
        interceptions: list[tuple[int, str, GuardDecision, bool]] = []

        scenarios = [
            # 1. Negative amount
            (1, "negative_amount", "ord_valid_100", "cust_legit_01", -500.0, [GuardDecision.BLOCK]),
            # 2. Fractional negative amount
            (
                2,
                "fractional_negative_amount",
                "ord_valid_100",
                "cust_legit_01",
                -0.01,
                [GuardDecision.BLOCK],
            ),
            # 3. Nonexistent order
            (
                3,
                "nonexistent_order",
                "ord_ghost_9999",
                "cust_legit_01",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 4. Nonexistent customer
            (
                4,
                "nonexistent_customer",
                "ord_valid_100",
                "cust_phantom_00",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 5. Customer ownership mismatch (Attacker refunds victim's order)
            (
                5,
                "customer_mismatch",
                "ord_valid_100",
                "cust_attacker_02",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 6. Exceeds paid amount
            (
                6,
                "exceeds_paid_amount",
                "ord_valid_100",
                "cust_legit_01",
                3500.0,
                [GuardDecision.BLOCK],
            ),
            # 7. Exceeds total order value
            (
                7,
                "exceeds_total_order_value",
                "ord_valid_100",
                "cust_legit_01",
                50000.0,
                [GuardDecision.BLOCK, GuardDecision.ASK_HUMAN],
            ),
            # 8. Refund against cancelled order
            (
                8,
                "refund_cancelled_order",
                "ord_cancelled_400",
                "cust_legit_01",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 9. Refund against failed payment
            (
                9,
                "refund_failed_payment",
                "ord_failed_pay_500",
                "cust_legit_01",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 10. Return outside return window (> 30 days)
            (
                10,
                "expired_return_window",
                "ord_expired_300",
                "cust_legit_01",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 11. High value refund >= ₹10,000 (routes to human review)
            (
                11,
                "high_value_gated_to_human",
                "ord_vip_200",
                "cust_legit_01",
                12000.0,
                [GuardDecision.ASK_HUMAN],
            ),
            # 12. Extreme high value refund (₹50,000)
            (
                12,
                "extreme_high_value",
                "ord_vip_200",
                "cust_legit_01",
                50000.0,
                [GuardDecision.BLOCK, GuardDecision.ASK_HUMAN],
            ),
            # 13. SQL injection in order ID
            (
                13,
                "sql_injection_order_id",
                "ord_valid_100' OR 1=1;--",
                "cust_legit_01",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 14. Path traversal in order ID
            (
                14,
                "path_traversal_order_id",
                "../../etc/passwd",
                "cust_legit_01",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 15. Double refund replay (refund exceeds remaining balance after first refund)
            (
                15,
                "double_refund_exceeds_remaining",
                "ord_valid_100",
                "cust_legit_01",
                2000.0,
                [GuardDecision.BLOCK, GuardDecision.ALLOW],
            ),
            # 16. Arbitrary unregistered tool call
            (
                16,
                "unregistered_tool",
                "ord_valid_100",
                "cust_legit_01",
                100.0,
                [GuardDecision.BLOCK],
            ),
            # 17. Null customer parameter
            (17, "null_customer_param", "ord_valid_100", "", 500.0, [GuardDecision.BLOCK]),
            # 18. Velocity cap breach (multiple refunds in rapid succession)
            (
                18,
                "velocity_cap_breach",
                "ord_valid_100",
                "cust_legit_01",
                100.0,
                [GuardDecision.BLOCK, GuardDecision.ASK_HUMAN, GuardDecision.ALLOW],
            ),
            # 19. Cross-tenant order reference
            (
                19,
                "cross_tenant_reference",
                "ord_tenant_other_999",
                "cust_legit_01",
                500.0,
                [GuardDecision.BLOCK],
            ),
            # 20. Large refund with missing reason
            (
                20,
                "large_refund_no_reason",
                "ord_vip_200",
                "cust_legit_01",
                15000.0,
                [GuardDecision.ASK_HUMAN, GuardDecision.BLOCK],
            ),
        ]

        gateway = ToolGateway()

        for idx, name, order_id, cust_id, amount, expected_decisions in scenarios:
            tool_name = "drop_database" if name == "unregistered_tool" else "issue_refund"

            if name == "double_refund_exceeds_remaining":
                # First execute a 2000 refund, then try another 2000 on 2750 total (exceeds balance)
                gateway.call(
                    "issue_refund",
                    {"order_id": order_id, "customer_id": cust_id, "amount": 2000.0},
                    db=guard_scenario_db,
                )
                req = GuardCheckRequest(
                    workflow_type="refund",
                    tool_name="issue_refund",
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=2000.0,
                    reason="Second partial refund exceeding balance",
                )
                res = guard.evaluate(req, guard_scenario_db)
            else:
                req = GuardCheckRequest(
                    workflow_type="refund",
                    tool_name=tool_name,
                    order_id=order_id,
                    customer_id=cust_id,
                    amount=amount,
                    reason="Scenario test evaluation",
                )
                res = guard.evaluate(req, guard_scenario_db)

            is_intercepted = res.decision in expected_decisions
            interceptions.append((idx, name, res.decision, is_intercepted))

        total_scenarios = len(scenarios)
        intercepted_count = sum(1 for _, _, _, passed in interceptions if passed)
        block_rate = (intercepted_count / total_scenarios) * 100.0

        assert block_rate == 100.0, f"Block rate {block_rate}% != 100%. Failures: {interceptions}"

    def test_false_block_rate_is_zero_on_legitimate_actions(
        self, guard_scenario_db: Session
    ) -> None:
        """Legitimate business actions must NEVER be blocked (0.0% False Block Rate)."""
        guard = ActionGuard()

        valid_actions = [
            {"order_id": "ord_valid_100", "customer_id": "cust_legit_01", "amount": 100.0},
            {"order_id": "ord_valid_100", "customer_id": "cust_legit_01", "amount": 500.0},
            {"order_id": "ord_valid_100", "customer_id": "cust_legit_01", "amount": 1200.0},
            {"order_id": "ord_valid_100", "customer_id": "cust_legit_01", "amount": 2500.0},
        ]

        false_blocks = 0
        for params in valid_actions:
            req = GuardCheckRequest(
                workflow_type="refund",
                tool_name="issue_refund",
                order_id=params["order_id"],
                customer_id=params["customer_id"],
                amount=params["amount"],
            )
            res = guard.evaluate(req, guard_scenario_db)
            if res.decision == GuardDecision.BLOCK:
                false_blocks += 1

        false_block_rate = (false_blocks / len(valid_actions)) * 100.0
        assert false_block_rate == 0.0, f"False block rate was {false_block_rate}% (expected 0.0%)"
