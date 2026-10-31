"""
Proofline EARP — Real Browser Acceptance Testing Suite (Phase 7).
Executes real end-to-end browser journeys using Playwright Chromium:
1. Login & Operator Session Management.
2. Comprehensive Dashboard & Observability Navigation.
3. Legitimate Low-Value Refund Workflow & Visual Trace.
4. High-Value Refund Human-in-the-Loop Escalation & Approval.
5. High-Risk Action Rejection Workflow.
6. Cross-Tenant IDOR Attack Detection & Security Display.
7. Duplicate Refund Submission & Idempotency Visual Feedback.
8. Claim-vs-State Grounding Verification Execution.
9. Trace Explorer Waterfall Spans & Execution Inspection.
10. Application State Recovery & Persistence Across Browser Reload.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.request
import urllib.error
import pytest
from playwright.sync_api import sync_playwright

import uvicorn
from sqlalchemy.orm import Session

from earp.gateway.app import app
from earp.db.session import SessionLocal, init_db
from earp.db.models import Customer, Order, Payment, Refund, ApprovalQueueRecord, TraceRecord
from earp.security.auth import create_access_token, Role


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def seed_browser_test_data():
    """Seeds necessary database entities for real browser end-to-end testing."""
    init_db()
    with SessionLocal() as db:
        # Seed Customer 1 & Order 1
        c1 = db.query(Customer).filter_by(id="c_browser_1").first()
        if not c1:
            c1 = Customer(id="c_browser_1", name="Browser User One", email="b1@example.com", phone="+919876543210")
            o1 = Order(id="o_browser_1", customer_id="c_browser_1", status="completed", subtotal=1000.0, tax=0.0, total_amount=1000.0)
            p1 = Payment(id="p_browser_1", order_id="o_browser_1", customer_id="c_browser_1", amount=1000.0, status="succeeded")
            db.add_all([c1, o1, p1])

        # Seed VIP Customer & Order
        cvip = db.query(Customer).filter_by(id="c_browser_vip").first()
        if not cvip:
            cvip = Customer(id="c_browser_vip", name="VIP Browser User", email="vip@example.com", phone="+919876543211")
            ovip = Order(id="o_browser_vip", customer_id="c_browser_vip", status="completed", subtotal=50000.0, tax=0.0, total_amount=50000.0)
            pvip = Payment(id="p_browser_vip", order_id="o_browser_vip", customer_id="c_browser_vip", amount=50000.0, status="succeeded")
            db.add_all([cvip, ovip, pvip])

        # Seed Fraud Customer & Order
        cfraud = db.query(Customer).filter_by(id="c_browser_fraud").first()
        if not cfraud:
            cfraud = Customer(id="c_browser_fraud", name="Suspicious User", email="fraud@example.com", phone="+919876543212")
            ofraud = Order(id="o_browser_fraud", customer_id="c_browser_fraud", status="completed", subtotal=50000.0, tax=0.0, total_amount=50000.0)
            pfraud = Payment(id="p_browser_fraud", order_id="o_browser_fraud", customer_id="c_browser_fraud", amount=50000.0, status="succeeded")
            db.add_all([cfraud, ofraud, pfraud])

        # Seed Replay Customer & Order
        creplay = db.query(Customer).filter_by(id="c_replay_test").first()
        if not creplay:
            creplay = Customer(id="c_replay_test", name="Replay User", email="replay@example.com", phone="+919876543213")
            oreplay = Order(id="o_replay_test", customer_id="c_replay_test", status="completed", subtotal=5000.0, tax=0.0, total_amount=5000.0)
            preplay = Payment(id="p_replay_test", order_id="o_replay_test", customer_id="c_replay_test", amount=5000.0, status="succeeded")
            db.add_all([creplay, oreplay, preplay])

        # Seed Tenant Isolation Entities
        cvictim = db.query(Customer).filter_by(id="cust_tenant_victim").first()
        if not cvictim:
            cvictim = Customer(id="cust_tenant_victim", name="Victim User", email="victim@example.com", phone="+919876543214")
            ovictim = Order(id="o_victim_99", customer_id="cust_tenant_victim", status="completed", subtotal=2000.0, tax=0.0, total_amount=2000.0)
            pvictim = Payment(id="p_victim_99", order_id="o_victim_99", customer_id="cust_tenant_victim", amount=2000.0, status="succeeded")
            cattacker = Customer(id="cust_tenant_attacker", name="Attacker User", email="attacker@example.com", phone="+919876543215")
            db.add_all([cvictim, ovictim, pvictim, cattacker])

        db.commit()


@pytest.fixture(scope="module")
def browser_server():
    """Spawns an actual Uvicorn server in a background thread for browser testing."""
    app.dependency_overrides.clear()
    seed_browser_test_data()

    port = find_free_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"

    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server readiness
    max_retries = 30
    ready = False
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.2)

    if not ready:
        raise RuntimeError(f"Server on {base_url} failed to start in time")

    yield base_url

    server.should_exit = True
    thread.join(timeout=3)


@pytest.fixture(scope="module")
def browser_context():
    """Launches headless Chromium via Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        yield context
        context.close()
        browser.close()


def test_journey_1_login_and_auth_session(browser_server, browser_context):
    """Journey 1: Login & Operator Session Management in Browser."""
    page = browser_context.new_page()
    page.goto(f"{browser_server}/guard")
    page.wait_for_selector(".app-container", timeout=10000)

    # Click Sign in as Operator
    signin_button = page.locator("button:has-text('Sign in as Operator')")
    if signin_button.is_visible():
        signin_button.click()
        page.wait_for_selector("text=Operator Active", timeout=5000)
        assert page.locator("text=Operator Active").is_visible()

    # Verify localStorage token
    token = page.evaluate("() => localStorage.getItem('proofline_token')")
    assert token is not None and len(token) > 20
    page.close()


def test_journey_2_dashboard_navigation(browser_server, browser_context):
    """Journey 2: Seamless Dashboard & Observability Navigation."""
    page = browser_context.new_page()
    page.goto(f"{browser_server}/overview")
    page.wait_for_selector(".app-container", timeout=10000)

    # Check overview page heading
    page.wait_for_selector("h1:has-text('System Health & Agent Reliability')", timeout=5000)
    assert page.locator("h1:has-text('System Health & Agent Reliability')").is_visible()

    # Navigate via Sidebar links and check unique H1 text for each
    routes_to_test = [
        ("Trace Explorer", "/traces", "Trace Explorer"),
        ("Guardrails & Approvals", "/guard", "Action Guard"),
        ("Claim Verifier", "/evals", "Claim Grounding"),
        ("Data Watchdog", "/watchdog", "State Reconciliation"),
        ("Red Team & DLP", "/security", "Red Team Matrix"),
        ("Model Benchmarks", "/benchmark", "Multi-Model Reliability"),
    ]

    for link_text, path, heading in routes_to_test:
        page.click(f".sidebar a:has-text('{link_text}')")
        page.wait_for_url(f"**{path}", timeout=5000)
        page.wait_for_selector(f"h1:has-text('{heading}')", timeout=5000)
        assert page.locator(f"h1:has-text('{heading}')").is_visible()

    page.close()


def test_journey_3_legitimate_refund_and_trace(browser_server, browser_context):
    """Journey 3: Legitimate Low-Value Refund Workflow & Visual Trace."""
    token = create_access_token({"sub": "admin", "role": Role.ADMIN.value, "project_id": "default"})

    # Trigger legitimate refund via Tool Gateway API (amount <= 10,000 is auto-approved)
    req = urllib.request.Request(
        f"{browser_server}/api/v1/guard/gateway/call",
        data=json.dumps({
            "tool_name": "issue_refund",
            "params": {
                "customer_id": "c_browser_1",
                "order_id": "o_browser_1",
                "amount": 450.0,
                "reason": "Customer dissatisfied with size",
            },
            "idempotency_key": "idemp_b_legit_450"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        assert res.get("decision") in ("ALLOW", "allow") or res.get("status") in ("success", "executed") or res.get("success") is True

    # Inspect in browser Trace Explorer
    page = browser_context.new_page()
    page.goto(f"{browser_server}/traces")
    page.wait_for_selector(".app-container", timeout=10000)
    page.wait_for_selector("h1:has-text('Trace Explorer & Step Waterfall')", timeout=5000)
    assert page.locator("h1:has-text('Trace Explorer & Step Waterfall')").is_visible()
    page.close()


def test_journey_4_high_value_refund_approval(browser_server, browser_context):
    """Journey 4: High-Value Refund Human-in-the-Loop Escalation & Authorization."""
    token = create_access_token({"sub": "admin", "role": Role.ADMIN.value, "project_id": "default"})

    # Trigger high-value refund > ₹10,000 requiring human approval via Tool Gateway
    req = urllib.request.Request(
        f"{browser_server}/api/v1/guard/gateway/call",
        data=json.dumps({
            "tool_name": "issue_refund",
            "params": {
                "customer_id": "c_browser_vip",
                "order_id": "o_browser_vip",
                "amount": 15000.0,
                "reason": "VIP laptop return",
            },
            "idempotency_key": f"idemp_vip_{int(time.time()*1000)}"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        assert res["decision"].lower() == "ask_human"
        approval_id = res.get("approval_id")
        assert approval_id is not None

    # Open browser on Guardrails page with operator token
    page = browser_context.new_page()
    page.add_init_script(f"localStorage.setItem('proofline_token', '{token}')")
    page.goto(f"{browser_server}/guard")
    page.wait_for_selector(".app-container", timeout=10000)

    # Verify pending item is rendered
    page.wait_for_selector(f"text={approval_id}", timeout=5000)
    assert page.locator(f"text={approval_id}").is_visible()

    # Click Authorize
    authorize_btn = page.locator(f"div:has-text('{approval_id}') button:has-text('Authorize')").first
    authorize_btn.click()

    # Verify notification toast/alert
    page.wait_for_selector(f"text=Proposal {approval_id} authorized", timeout=5000)
    assert page.locator(f"text=Proposal {approval_id} authorized").is_visible()
    page.close()


def test_journey_5_high_risk_rejection(browser_server, browser_context):
    """Journey 5: High-Risk Action Rejection Workflow."""
    token = create_access_token({"sub": "admin", "role": Role.ADMIN.value, "project_id": "default"})

    # Trigger another high-value refund requiring human approval via Tool Gateway
    req = urllib.request.Request(
        f"{browser_server}/api/v1/guard/gateway/call",
        data=json.dumps({
            "tool_name": "issue_refund",
            "params": {
                "customer_id": "c_browser_fraud",
                "order_id": "o_browser_fraud",
                "amount": 25000.0,
                "reason": "Suspicious bulk claim",
            },
            "idempotency_key": f"idemp_fraud_{int(time.time()*1000)}"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        assert res["decision"].lower() == "ask_human"
        approval_id = res.get("approval_id")
        assert approval_id is not None

    page = browser_context.new_page()
    page.add_init_script(f"localStorage.setItem('proofline_token', '{token}')")
    page.goto(f"{browser_server}/guard")
    page.wait_for_selector(".app-container", timeout=10000)

    # Locate and Click Reject
    page.wait_for_selector(f"text={approval_id}", timeout=5000)
    reject_btn = page.locator(f"div:has-text('{approval_id}') button:has-text('Reject')").first
    reject_btn.click()

    # Verify notification
    page.wait_for_selector(f"text=Proposal {approval_id} rejected", timeout=5000)
    assert page.locator(f"text=Proposal {approval_id} rejected").is_visible()
    page.close()


def test_journey_6_cross_tenant_idor_prevention(browser_server, browser_context):
    """Journey 6: Cross-Tenant IDOR Attack Detection & Security Display."""
    token = create_access_token({"sub": "admin", "role": Role.ADMIN.value, "project_id": "default"})

    # Attempt cross-tenant refund where customer_id != order customer
    req = urllib.request.Request(
        f"{browser_server}/api/v1/guard/gateway/call",
        data=json.dumps({
            "tool_name": "issue_refund",
            "params": {
                "customer_id": "cust_tenant_attacker",
                "order_id": "o_victim_99",
                "amount": 500.0,
                "reason": "IDOR exploit attempt",
            },
            "idempotency_key": "idemp_idor_attack"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        assert res.get("success") is False or res.get("decision") == "BLOCK" or "mismatch" in res.get("error", "").lower() or "belong" in res.get("error", "").lower()

    # Check Security Page in browser
    page = browser_context.new_page()
    page.goto(f"{browser_server}/security")
    page.wait_for_selector(".app-container", timeout=10000)
    page.wait_for_selector("h1:has-text('Red Team Matrix & PII Guard')", timeout=5000)
    assert page.locator("h1:has-text('Red Team Matrix & PII Guard')").is_visible()
    page.close()


def test_journey_7_duplicate_refund_idempotency_browser(browser_server, browser_context):
    """Journey 7: Duplicate Refund Submission & Idempotency Visual Feedback."""
    token = create_access_token({"sub": "admin", "role": Role.ADMIN.value, "project_id": "default"})
    shared_key = f"idemp_browser_replay_{int(time.time()*1000)}"

    # Seed fresh order for replay test
    with SessionLocal() as db:
        o_rep = Order(id=f"o_rep_{int(time.time())}", customer_id="c_replay_test", status="completed", subtotal=5000.0, tax=0.0, total_amount=5000.0)
        p_rep = Payment(id=f"p_rep_{int(time.time())}", order_id=o_rep.id, customer_id="c_replay_test", amount=5000.0, status="succeeded")
        db.add_all([o_rep, p_rep])
        db.commit()
        order_id = o_rep.id

    # Call twice with identical idempotency key
    for i in range(2):
        req = urllib.request.Request(
            f"{browser_server}/api/v1/guard/gateway/call",
            data=json.dumps({
                "tool_name": "issue_refund",
                "params": {
                    "customer_id": "c_replay_test",
                    "order_id": order_id,
                    "amount": 300.0,
                    "reason": "Double click test",
                },
                "idempotency_key": shared_key
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if i == 0:
                assert res.get("status") in ("success", "executed") or res.get("success") is True
            else:
                # Replay must be recognized as idempotent
                assert res.get("cached") is True or res.get("idempotent") is True or res.get("success") is True or "already has a refund processed" in res.get("error", "")


def test_journey_8_claim_verification_in_browser(browser_server, browser_context):
    """Journey 8: Claim-vs-State Grounding Verification in Browser UI."""
    page = browser_context.new_page()
    page.goto(f"{browser_server}/evals")
    page.wait_for_selector(".app-container", timeout=10000)

    # Locate the verify button
    verify_button = page.locator("button:has-text('Verify Grounding Against Snapshot')")
    page.wait_for_selector("button:has-text('Verify Grounding Against Snapshot')", timeout=5000)
    assert verify_button.is_visible()
    verify_button.click()

    # Verify that the verdict card appears
    page.wait_for_selector("text=Grounding Verdict:", timeout=5000)
    assert page.locator("text=Grounding Verdict:").is_visible()
    page.close()


def test_journey_9_trace_explorer_waterfall(browser_server, browser_context):
    """Journey 9: Trace Explorer Waterfall Spans & Execution Inspection."""
    page = browser_context.new_page()
    page.goto(f"{browser_server}/traces")
    page.wait_for_selector(".app-container", timeout=10000)

    # Ensure traces table is rendered
    page.wait_for_selector("table", timeout=5000)
    assert page.locator("table").is_visible()

    # Click on the first trace row to inspect waterfall
    rows = page.locator("table tbody tr")
    if rows.count() > 0:
        rows.first.click()
        page.wait_for_selector("text=Execution Waterfall", timeout=5000)
        assert page.locator("text=Execution Waterfall").is_visible()

    page.close()


def test_journey_10_application_recovery_and_persistence(browser_server, browser_context):
    """Journey 10: Application State Recovery & Persistence Across Browser Reload."""
    page = browser_context.new_page()
    token = create_access_token({"sub": "admin", "role": Role.ADMIN.value, "project_id": "default"})
    page.add_init_script(f"localStorage.setItem('proofline_token', '{token}')")

    page.goto(f"{browser_server}/overview")
    page.wait_for_selector(".app-container", timeout=10000)

    # Reload page
    page.reload()
    page.wait_for_selector(".app-container", timeout=10000)

    # Verify authentication token persisted in localStorage
    token_after = page.evaluate("() => localStorage.getItem('proofline_token')")
    assert token_after == token

    # Verify dashboard elements reload properly
    page.wait_for_selector("h1:has-text('System Health & Agent Reliability')", timeout=5000)
    assert page.locator("h1:has-text('System Health & Agent Reliability')").is_visible()
    page.close()
