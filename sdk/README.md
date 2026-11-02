# Argvtix SDK

Zero-overhead, production-grade observability and policy enforcement SDK for AI Agents.

## Installation

```bash
pip install argvtix-sdk
```

## Quick Start

### 1. Auto-Instrument Agent Functions with `@trace`

```python
from argvtix_sdk import trace


@trace(workflow="refund_processing")
def handle_customer_refund(order_id: str, amount: float):
    # Function execution, inputs, returns, and latency are automatically captured
    return {"status": "success", "refund_id": "RF-100"}
```

### 2. Client & Tool Gateway Integration

```python
from argvtix_sdk import ArgvtixClient, ToolGatewayClient

client = ArgvtixClient(api_url="http://localhost:8000", project_id="shopops")
gateway = ToolGatewayClient(client=client)

# Execute writes safely through the zero-bypass policy gate
result = gateway.call_tool(
    tool_name="issue_refund",
    parameters={"order_id": "ORD-101", "amount": 2500.0},
    agent_id="agent-v1",
)
```
