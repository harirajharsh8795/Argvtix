"""Proofline SDK: Zero-overhead agent observability and policy guard proxy."""

from proofline_sdk.client import ProoflineClient, ProoflineClientError
from proofline_sdk.gateway import GatewayExecutionResult, ToolGatewayClient
from proofline_sdk.trace import (
    get_default_client,
    local_trace_buffer,
    set_default_client,
    trace,
)

__version__ = "0.1.0"
__all__ = [
    "trace",
    "ProoflineClient",
    "ProoflineClientError",
    "ToolGatewayClient",
    "GatewayExecutionResult",
    "local_trace_buffer",
    "set_default_client",
    "get_default_client",
]
