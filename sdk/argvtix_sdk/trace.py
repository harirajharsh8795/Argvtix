"""Trace auto-instrumentation decorator for Python agent workflows."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import functools
import inspect
import time
from typing import Any, Callable, Optional
import uuid

from argvtix_sdk.client import ArgvtixClient

# In-memory buffer for recorded traces during offline runs or local verification
local_trace_buffer: list[dict[str, Any]] = []
_default_client: Optional[ArgvtixClient] = None


def set_default_client(client: ArgvtixClient) -> None:
    """Configures global default Argvtix client for auto-instrumentation."""
    global _default_client
    _default_client = client


def get_default_client() -> Optional[ArgvtixClient]:
    return _default_client


def trace(
    workflow: str = "agent_execution",
    step_type: str = "tool",
    client: Optional[ArgvtixClient] = None,
    record_args: bool = True,
    record_result: bool = True,
) -> Callable:
    """Decorator that auto-instruments Python functions with Argvtix trace telemetry.

    Supports both synchronous and asynchronous functions.
    """
    def decorator(fn: Callable) -> Callable:
        fn_name = fn.__name__

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            active_client = client or _default_client
            trace_id = f"TRC-{uuid.uuid4().hex[:12]}"
            step_id = f"STP-{uuid.uuid4().hex[:8]}"

            start_utc = datetime.now(timezone.utc)
            start_mono = time.monotonic()

            inputs_data = {}
            if record_args:
                sig = inspect.signature(fn)
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                inputs_data = {k: str(v)[:500] for k, v in bound.arguments.items()}

            error_msg = None
            result_data = None
            status_str = "SUCCESS"

            try:
                result = fn(*args, **kwargs)
                if record_result:
                    result_data = str(result)[:1000]
                return result
            except Exception as e:
                status_str = "ERROR"
                error_msg = str(e)
                raise
            finally:
                latency_ms = (time.monotonic() - start_mono) * 1000.0
                trace_payload = {
                    "trace_id": trace_id,
                    "session_id": f"SES-{uuid.uuid4().hex[:8]}",
                    "workflow": workflow,
                    "status": status_str,
                    "total_latency_ms": round(latency_ms, 2),
                    "started_at": start_utc.isoformat(),
                    "steps": [
                        {
                            "step_id": step_id,
                            "step_type": step_type,
                            "name": fn_name,
                            "latency_ms": round(latency_ms, 2),
                            "inputs": inputs_data,
                            "outputs": {"result": result_data} if result_data is not None else None,
                            "error": error_msg,
                        }
                    ],
                }

                local_trace_buffer.append(trace_payload)
                if active_client:
                    try:
                        active_client.log_trace(trace_payload)
                    except Exception:
                        pass

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            active_client = client or _default_client
            trace_id = f"TRC-{uuid.uuid4().hex[:12]}"
            step_id = f"STP-{uuid.uuid4().hex[:8]}"

            start_utc = datetime.now(timezone.utc)
            start_mono = time.monotonic()

            inputs_data = {}
            if record_args:
                sig = inspect.signature(fn)
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                inputs_data = {k: str(v)[:500] for k, v in bound.arguments.items()}

            error_msg = None
            result_data = None
            status_str = "SUCCESS"

            try:
                result = await fn(*args, **kwargs)
                if record_result:
                    result_data = str(result)[:1000]
                return result
            except Exception as e:
                status_str = "ERROR"
                error_msg = str(e)
                raise
            finally:
                latency_ms = (time.monotonic() - start_mono) * 1000.0
                trace_payload = {
                    "trace_id": trace_id,
                    "session_id": f"SES-{uuid.uuid4().hex[:8]}",
                    "workflow": workflow,
                    "status": status_str,
                    "total_latency_ms": round(latency_ms, 2),
                    "started_at": start_utc.isoformat(),
                    "steps": [
                        {
                            "step_id": step_id,
                            "step_type": step_type,
                            "name": fn_name,
                            "latency_ms": round(latency_ms, 2),
                            "inputs": inputs_data,
                            "outputs": {"result": result_data} if result_data is not None else None,
                            "error": error_msg,
                        }
                    ],
                }

                local_trace_buffer.append(trace_payload)
                if active_client:
                    try:
                        active_client.log_trace(trace_payload)
                    except Exception:
                        pass

        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper

    return decorator
