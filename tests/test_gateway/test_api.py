"""
Test Suite for FastAPI Gateway Endpoints
Tests:
- GET /health
- POST /api/v1/traces
- GET /api/v1/traces
- GET /api/v1/traces/{trace_id}
- GET /api/v1/traces/stats
- POST /api/v1/guard/check
- POST /api/v1/watchdog/scan
- GET /api/v1/watchdog/findings
- PATCH /api/v1/watchdog/findings/{id}/resolve
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, Customer, Order, Payment, WatchdogFindingRecord
from argvtix.db.session import get_db
from argvtix.gateway.app import app
from argvtix.trace.schemas import (
    GuardDecision,
    LLMCallData,
    StepType,
    Trace,
    TraceStatus,
    TraceStep,
)

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Baseline customer & order
    cust = Customer(id="cust_api_1", name="Anita Roy", email="anita@example.com")
    db.add(cust)
    order = Order(
        id="ord_api_1",
        customer_id="cust_api_1",
        status="completed",
        subtotal=5000.0,
        tax=900.0,
        total_amount=5900.0,
    )
    db.add(order)
    db.add(
        Payment(
            id="pmt_api_1",
            order_id="ord_api_1",
            customer_id="cust_api_1",
            amount=5900.0,
            status="succeeded",
        )
    )
    # High-value order (>₹10,000) for approval workflow tests
    order_high = Order(
        id="ord_api_high",
        customer_id="cust_api_1",
        status="completed",
        subtotal=22000.0,
        tax=3000.0,
        total_amount=25000.0,
    )
    db.add(order_high)
    db.add(
        Payment(
            id="pmt_api_high",
            order_id="ord_api_high",
            customer_id="cust_api_1",
            amount=25000.0,
            status="succeeded",
        )
    )
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"]["connected"] is True


def test_ingest_and_get_trace(client: TestClient) -> None:
    sample_trace = Trace(
        trace_id="tr_api_test_01",
        customer_id="cust_api_1",
        session_id="sess_123",
        input_text="Help me with refund for order 1042",
        prompt_version="v1.0",
        model_version="gemini-1.5-flash",
        status=TraceStatus.COMPLETED,
        tags=["refund"],
        metadata={"workflow_type": "refund"},
        steps=[
            TraceStep(
                step_id="step_01",
                step_index=0,
                step_type=StepType.LLM_CALL,
                duration_ms=250.0,
                llm_call=LLMCallData(
                    model="gemini-1.5-flash",
                    prompt_version="v1",
                    input_text="Verify refund request",
                    output_text="Refund approved",
                    input_tokens=100,
                    output_tokens=50,
                    cost_usd=0.0002,
                ),
            )
        ],
    )

    # POST ingest
    post_res = client.post("/api/v1/traces", json=sample_trace.model_dump(mode="json"))
    assert post_res.status_code == 201
    assert post_res.json()["trace_id"] == "tr_api_test_01"

    # GET by ID
    get_res = client.get("/api/v1/traces/tr_api_test_01")
    assert get_res.status_code == 200
    trace_data = get_res.json()
    assert trace_data["workflow_type"] == "refund"
    assert len(trace_data["steps"]) == 1
    assert trace_data["steps"][0]["step_type"] == "llm_call"

    # GET list
    list_res = client.get("/api/v1/traces")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # GET stats
    stats_res = client.get("/api/v1/traces/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["total_traces"] >= 1


def test_guard_check_endpoint(client: TestClient) -> None:
    payload = {
        "workflow_type": "refund",
        "tool_name": "issue_refund",
        "customer_id": "cust_api_1",
        "order_id": "ord_api_1",
        "amount": 2000.0,
    }
    res = client.post("/api/v1/guard/check", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == GuardDecision.ALLOW.value


def test_watchdog_scan_and_resolve(client: TestClient) -> None:
    # 1. Seed a finding manually or via scan
    db = TestingSessionLocal()
    rec = WatchdogFindingRecord(
        id="find_test_99",
        rule_name="duplicate_refund",
        severity="high",
        description="Duplicate refund test",
        entity_type="order",
        entity_id="ord_api_1",
        resolved=False,
    )
    db.add(rec)
    db.commit()
    db.close()

    # Query findings
    res = client.get("/api/v1/watchdog/findings")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1

    # Resolve finding
    patch_res = client.patch("/api/v1/watchdog/findings/find_test_99/resolve")
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "success"


def test_evals_run_endpoint(client: TestClient) -> None:
    res = client.post("/api/v1/evals/run", json={"workflow": "balance", "max_cases": 2})
    assert res.status_code == 200
    data = res.json()
    assert data["total_evals"] == 2
    assert "overall_accuracy" in data
    assert "p50_latency_ms" in data


def test_evals_regression_endpoint(client: TestClient) -> None:
    res = client.post(
        "/api/v1/evals/regression", json={"workflow": "balance", "max_drop_allowed": 10.0}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] in ("PASSED", "FAILED_REGRESSION")
    assert "accuracy_delta" in data
    assert "regressions_count" in data


def test_evals_verify_claims_endpoint(client: TestClient) -> None:
    payload = {
        "agent_response": "Your refund of ₹500 for order ORD-1042 has been successfully issued.",
        "tool_records": [
            {
                "tool_name": "issue_refund",
                "tool_args": {"order_id": "ORD-1042", "amount": 500},
                "tool_result": {
                    "status": "completed",
                    "refunded_amount": 500,
                    "order_id": "ORD-1042",
                },
                "is_success": True,
            }
        ],
    }
    res = client.post("/api/v1/evals/verify-claims", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_claims"] >= 1
    assert data["verified_count"] >= 1
    assert data["violations_count"] == 0
    assert data["accuracy_percent"] == 100.0


def test_evals_planted_scenarios_endpoint(client: TestClient) -> None:
    res = client.get("/api/v1/evals/planted-scenarios")
    assert res.status_code == 200
    data = res.json()
    assert data["total_scenarios"] >= 30
    assert len(data["scenarios"]) >= 30


def test_evals_passk_endpoint(client: TestClient) -> None:
    res = client.post("/api/v1/evals/passk", json={"k": 3, "workflow": "balance"})
    assert res.status_code == 200
    data = res.json()
    assert data["k"] == 3
    assert "pass_at_1" in data
    assert "pass_at_k" in data
    assert "pass_hat_k" in data
    assert "flake_rate" in data
    assert "reliability_index" in data


def test_gateway_call_allowed_tool(client: TestClient) -> None:
    res = client.post(
        "/api/v1/guard/gateway/call",
        json={
            "tool_name": "get_order",
            "params": {"order_id": "ord_api_1"},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "allow"
    assert data["success"] is True


def test_gateway_call_blocked_tool(client: TestClient) -> None:
    res = client.post(
        "/api/v1/guard/gateway/call",
        json={
            "tool_name": "issue_refund",
            "params": {
                "order_id": "ord_nonexistent_99",
                "customer_id": "cust_api_1",
                "amount": 500.0,
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "block"
    assert data["success"] is False
    assert "does not exist" in data["error"]


def test_gateway_approvals_flow(client: TestClient) -> None:
    # 1. Trigger high-value refund to enqueue approval
    res = client.post(
        "/api/v1/guard/gateway/call",
        json={
            "tool_name": "issue_refund",
            "params": {"order_id": "ord_api_high", "customer_id": "cust_api_1", "amount": 15000.0},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "ask_human"
    assert data["status"] == "pending_approval"
    approval_id = data["approval_id"]
    assert approval_id is not None

    # 2. List approvals
    list_res = client.get("/api/v1/guard/approvals?status=pending")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(a["id"] == approval_id for a in list_data["approvals"])

    # 3. Approve request
    appr_res = client.post(
        f"/api/v1/guard/approvals/{approval_id}/approve",
        json={"reviewer_id": "admin_user", "notes": "Approved for VIP customer"},
    )
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["status"] == "success"
    assert appr_data["approval_status"] == "approved"


def test_auth_token_issue_endpoint(client: TestClient) -> None:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": "dev_test", "password": "any", "project_id": "proj_1", "role": "admin"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["project_id"] == "proj_1"


def test_watchdog_anomaly_report_endpoint(client: TestClient) -> None:
    res = client.get("/api/v1/watchdog/anomaly/report")
    assert res.status_code == 200
    data = res.json()
    assert "total_points_analyzed" in data
    assert "is_anomalous" in data


def test_watchdog_reconcile_endpoint(client: TestClient) -> None:
    res = client.post(
        "/api/v1/watchdog/reconcile",
        json={
            "external_states": [
                {
                    "order_id": "ord_api_1",
                    "crm_invoice_amount": 1200.0,
                    "erp_order_status": "delivered",
                }
            ],
            "persist_findings": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "total_entities_checked" in data
    assert "is_synchronized" in data


def test_watchdog_alerts_endpoints(client: TestClient) -> None:
    # 1. Post a manual alert
    res = client.post(
        "/api/v1/watchdog/alerts",
        json={
            "title": "API Test Alert",
            "message": "Testing alert endpoint",
            "severity": "critical",
            "source": "test_suite",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "alert_id" in data

    # 2. Get alerts
    list_res = client.get("/api/v1/watchdog/alerts?limit=10")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total_alerts"] >= 1
    assert any(a["title"] == "API Test Alert" for a in list_data["alerts"])


def test_spend_summary_endpoint(client: TestClient) -> None:
    res = client.get("/api/v1/spend/summary")
    assert res.status_code == 200
    data = res.json()
    assert "daily_spend_usd" in data
    assert "monthly_spend_usd" in data
    assert "is_capped" in data


def test_contact_submission_success(client: TestClient) -> None:
    payload = {
        "name": "Alex Mercer",
        "email": "alex@enterprise-agents.ai",
        "company": "Apex Dynamics Corp",
        "use_case": "We are deploying autonomous customer refund agents and require sub-millisecond Action Guard policy verification and real-time PII DLP redaction.",
        "turnstile_token": "test-token-bypass",
    }
    res = client.post("/api/v1/contact", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "success"
    assert data["submission_id"].startswith("sub_")
    assert "24 business hours" in data["message"]


def test_contact_submission_honeypot_blocked(client: TestClient) -> None:
    payload = {
        "name": "Spam Bot",
        "email": "spambot@spam.com",
        "company": "Spam Corp",
        "use_case": "Buy cheap pharmaceutical products now with discount coupons.",
        "honeypot": "https://spamlink.com/payload",
    }
    res = client.post("/api/v1/contact", json=payload)
    assert res.status_code == 400
    assert "Automated submission detected" in res.json()["detail"]


def test_contact_submission_validation_error(client: TestClient) -> None:
    payload = {
        "name": "Jane",
        "email": "not-an-email",
        "company": "Acme",
        "use_case": "Too short",
    }
    res = client.post("/api/v1/contact", json=payload)
    assert res.status_code == 422
