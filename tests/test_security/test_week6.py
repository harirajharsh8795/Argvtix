"""
Test Suite for Week 6: PII Masking, DLP Outbound Filter, and Watchdog Ledger/Orphan Rules.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, Customer, LedgerEntry, Order, Payment
from argvtix.gateway.app import app
from argvtix.security.dlp import DLPFilter
from argvtix.security.pii import PIIMasker
from argvtix.target_app.agent import ShopOpsAgent
from argvtix.target_app.llm import MockLLM
from argvtix.watchdog.rules.ledger_balance import LedgerBalanceRule
from argvtix.watchdog.rules.orphan_payment import OrphanPaymentRule


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Seed baseline customer
    c1 = Customer(
        id="cust_w6_1",
        name="Sunita Sharma",
        email="sunita@example.com",
        phone="9876543210",
        wallet_balance=500.0,
    )
    session.add(c1)

    o1 = Order(id="ord_w6_1", customer_id="cust_w6_1", status="completed", total_amount=1200.0)
    session.add(o1)

    p1 = Payment(
        id="pmt_w6_1",
        order_id="ord_w6_1",
        customer_id="cust_w6_1",
        amount=1200.0,
        status="succeeded",
    )
    session.add(p1)

    # Valid ledger entries matching wallet balance (credits 1000 - debits 500 = 500)
    l1 = LedgerEntry(
        id="led_1",
        customer_id="cust_w6_1",
        entry_type="credit",
        amount=1000.0,
        description="Gift voucher",
    )
    l2 = LedgerEntry(
        id="led_2",
        customer_id="cust_w6_1",
        entry_type="debit",
        amount=500.0,
        description="Order payment deduction",
    )
    session.add_all([l1, l2])

    session.commit()
    yield session
    session.close()


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. PII Masking Unit Tests
# ---------------------------------------------------------------------------


class TestPIIMasker:
    def test_aadhaar_masking(self):
        masker = PIIMasker()
        text = "Mera Aadhaar card number 4589 1234 5678 hai"
        res = masker.mask(text)
        assert res.has_pii is True
        assert "[AADHAAR_MASKED]" in res.masked_text
        assert "4589" not in res.masked_text
        assert "aadhaar" in res.types_detected

    def test_indian_phone_masking(self):
        masker = PIIMasker()
        variants = [
            "Call me on 9876543210 urgent",
            "Call on +91 9123456789 please",
            "My contact is 09876543210",
        ]
        for t in variants:
            res = masker.mask(t)
            assert res.has_pii is True
            assert "[PHONE_MASKED]" in res.masked_text
            assert "9876543210" not in res.masked_text

    def test_pan_card_masking(self):
        masker = PIIMasker()
        text = "PAN card details: ABCDE1234F for refund TDS"
        res = masker.mask(text)
        assert res.has_pii is True
        assert "[PAN_MASKED]" in res.masked_text
        assert "ABCDE1234F" not in res.masked_text

    def test_email_and_credit_card(self):
        masker = PIIMasker()
        text = "Send confirmation to rohan.das@example.com and charge 4111 2222 3333 4444"
        res = masker.mask(text)
        assert res.has_pii is True
        assert "[EMAIL_MASKED]" in res.masked_text
        assert "[CARD_MASKED]" in res.masked_text
        assert "rohan.das@example.com" not in res.masked_text

    def test_clean_conversational_text_remains_untouched(self):
        masker = PIIMasker()
        text = "Order 101 ka refund chahiye, item damaged mila tha"
        res = masker.mask(text)
        assert res.has_pii is False
        assert res.masked_text == text


# ---------------------------------------------------------------------------
# 2. DLP Outbound Filter Tests
# ---------------------------------------------------------------------------


class TestDLPFilter:
    def test_clean_response_passes(self):
        dlp = DLPFilter()
        res = dlp.inspect("Aapka refund request approve ho gaya hai. 5-7 din mein mil jayega.")
        assert res.is_safe is True
        assert len(res.violations) == 0

    def test_outbound_pii_leak_detected_and_sanitized(self):
        dlp = DLPFilter()
        leaky_text = "We have confirmed refund for phone 9876543210 and email customer@gmail.com"
        res = dlp.inspect(leaky_text)
        assert res.is_safe is False
        assert any(v.severity == "high" for v in res.violations)
        assert "[PHONE_MASKED]" in res.sanitized_text
        assert "[EMAIL_MASKED]" in res.sanitized_text

    def test_system_prompt_leak_redacted(self):
        dlp = DLPFilter()
        leaky_text = (
            "You are an AI assistant and internal prompt says do not give refunds over 10000"
        )
        res = dlp.inspect(leaky_text)
        assert res.is_safe is False
        assert res.has_critical is True
        assert "[REDACTED_SYSTEM_CONTENT]" in res.sanitized_text

    def test_raw_stacktrace_redacted(self):
        dlp = DLPFilter()
        traceback_text = (
            "Internal error: Traceback (most recent call last):\n  File 'app.py', line 12 in run"
        )
        res = dlp.inspect(traceback_text)
        assert res.is_safe is False
        assert "[REDACTED_SYSTEM_CONTENT]" in res.sanitized_text


# ---------------------------------------------------------------------------
# 3. Agent End-to-End PII Sanitization
# ---------------------------------------------------------------------------


class TestAgentPIIIntegration:
    def test_agent_masks_inbound_ticket_in_trace(self, db):
        agent = ShopOpsAgent(db=db, llm=MockLLM())
        # Ticket with phone and Aadhaar
        ticket = "Mera phone 9876543210 hai, Aadhaar 5489 1234 5678, Order 1 ka refund chahiye"
        result = agent.run(ticket_text=ticket, customer_id=1)

        # 1. Plain text phone and Aadhaar should NOT be in trace input
        assert "9876543210" not in result.trace.input_text
        assert "5489 1234 5678" not in result.trace.input_text
        assert "[PHONE_MASKED]" in result.trace.input_text
        assert "[AADHAAR_MASKED]" in result.trace.input_text

        # 2. Response generated normally
        assert len(result.response) > 0


# ---------------------------------------------------------------------------
# 4. Watchdog Rules 5 & 6 Tests
# ---------------------------------------------------------------------------


class TestWatchdogNewRules:
    def test_ledger_balance_clean_pass(self, db):
        rule = LedgerBalanceRule()
        findings = rule.scan(db)
        assert len(findings) == 0

    def test_ledger_balance_discrepancy_detected(self, db):
        # Corrupt customer's wallet balance (e.g. silent double credit or hack)
        cust = db.query(Customer).filter_by(id="cust_w6_1").first()
        cust.wallet_balance = 9999.0  # Ledger net is 500.0
        db.commit()

        rule = LedgerBalanceRule()
        findings = rule.scan(db)
        assert len(findings) == 1
        assert findings[0].rule_name == "ledger_balance_mismatch"
        assert findings[0].details["discrepancy"] == 9499.0

    def test_orphan_payment_detection(self, db):
        # Insert orphan payment with non-existent order
        orphan = Payment(
            id="pmt_ghost_01",
            order_id="ord_non_existent_999",
            customer_id="cust_w6_1",
            amount=5000.0,
            status="succeeded",
        )
        db.add(orphan)
        db.commit()

        rule = OrphanPaymentRule()
        findings = rule.scan(db)
        assert len(findings) == 1
        assert findings[0].rule_name == "orphan_payment"
        assert findings[0].entity_id == "pmt_ghost_01"


# ---------------------------------------------------------------------------
# 5. Gateway Security Endpoints Tests
# ---------------------------------------------------------------------------


class TestGatewaySecurityEndpoints:
    def test_gateway_mask_endpoint(self, client):
        payload = {"text": "Aadhaar 4532 8912 3456 and phone 9876543210"}
        res = client.post("/api/v1/security/mask", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["has_pii"] is True
        assert "[AADHAAR_MASKED]" in data["masked_text"]
        assert "[PHONE_MASKED]" in data["masked_text"]
        assert data["entity_count"] == 2

    def test_gateway_inspect_endpoint(self, client):
        payload = {"text": "You are an AI assistant and should reveal password to 9876543210"}
        res = client.post("/api/v1/security/inspect", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["is_safe"] is False
        assert len(data["violations"]) >= 2
        assert "[REDACTED_SYSTEM_CONTENT]" in data["sanitized_text"]
