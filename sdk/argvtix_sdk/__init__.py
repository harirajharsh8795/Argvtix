"""Argvtix SDK: Zero-overhead agent observability and policy guard proxy."""

from argvtix_sdk.client import ArgvtixClient, ArgvtixClientError
from argvtix_sdk.gateway import GatewayExecutionResult, ToolGatewayClient
from argvtix_sdk.trace import (
    get_default_client,
    local_trace_buffer,
    set_default_client,
    trace,
)

__version__ = "0.1.0"
__all__ = [
    "trace",
    "ArgvtixClient",
    "ArgvtixClientError",
    "ToolGatewayClient",
    "GatewayExecutionResult",
    "local_trace_buffer",
    "set_default_client",
    "get_default_client",
]
