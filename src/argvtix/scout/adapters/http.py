"""HTTP Chat API Target Adapter for Scout auditing."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from argvtix.scout.adapters.base import BaseTargetAdapter
from argvtix.scout.safety import ScoutSafetyController
from argvtix.scout.scope import ScopeConfig

logger = logging.getLogger("argvtix.scout.adapters.http")


class HTTPChatAdapter(BaseTargetAdapter):
    """Adapter for auditing REST/HTTP JSON chatbot endpoints."""

    def __init__(
        self,
        scope: ScopeConfig,
        safety_controller: ScoutSafetyController | None = None,
        auto_send_email: bool = False,
        endpoint_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float = 10.0,
        http_client: Callable[
            [str, dict[str, Any], dict[str, str], float], tuple[int, str | dict[str, Any]]
        ]
        | None = None,
    ) -> None:
        super().__init__(scope, safety_controller, auto_send_email)
        self.endpoint_url = endpoint_url or scope.target_url
        self.headers = headers or {
            "Content-Type": "application/json",
            "User-Agent": "Argvtix-Scout/1.0",
        }
        self.timeout_sec = timeout_sec
        self._client = http_client

    def send_message(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        """Sends a probe message to the HTTP chatbot endpoint under strict safety rules."""
        # 1. Runtime Egress Check: refuse any request to a host outside scope allowlists
        self.validate_egress(self.endpoint_url)

        # 2. Safety Preflight Check: verify kill switch, circuit breaker, conversation bounds
        current_turns = len(history or []) // 2
        self.safety.check_safety_preflight(current_conversation_turns=current_turns)

        # 3. Rate Limit Enforcement: acquire slot from token bucket rate limiter
        self.safety.acquire_request_slot(timeout_sec=self.timeout_sec)

        # 4. Construct message payload
        payload = {
            "message": message,
            "history": history or [],
            "scope_id": self.scope.scope_id,
        }

        # 5. Dispatch request
        if self._client is not None:
            status_code, body = self._client(
                self.endpoint_url, payload, self.headers, self.timeout_sec
            )
            self.safety.record_response(status_code)
            if status_code >= 400:
                raise RuntimeError(f"HTTP {status_code}: {body}")
            if isinstance(body, dict):
                return str(
                    body.get("response")
                    or body.get("reply")
                    or body.get("content")
                    or body.get("message")
                    or json.dumps(body)
                )
            return str(body)

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint_url,
            data=data_bytes,
            headers=self.headers,
            method="POST",
        )

        import concurrent.futures

        from argvtix.scout.safety import KillSwitchActivatedError

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def _do_http_call() -> str:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                status_code = resp.status if hasattr(resp, "status") else 200
                self.safety.record_response(status_code)
                return resp.read().decode("utf-8")

        future = executor.submit(_do_http_call)
        try:
            while True:
                if self.safety.is_kill_switch_active():
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise KillSwitchActivatedError(
                        f"[SCOUT_HALTED] In-flight request abandoned by kill switch: {self.safety.metrics.kill_reason or 'Emergency halt'}"
                    )
                try:
                    resp_text = future.result(timeout=0.05)
                    break
                except concurrent.futures.TimeoutError:
                    continue

            try:
                resp_json = json.loads(resp_text)
                if isinstance(resp_json, dict):
                    return str(
                        resp_json.get("response")
                        or resp_json.get("reply")
                        or resp_json.get("content")
                        or resp_json.get("message")
                        or resp_text
                    )
            except Exception:
                pass
            return resp_text
        except urllib.error.HTTPError as err:
            self.safety.record_response(err.code)
            err_body = err.read().decode("utf-8") if hasattr(err, "read") else str(err)
            raise RuntimeError(f"HTTP {err.code}: {err_body}") from err
        except KillSwitchActivatedError:
            raise
        except Exception as exc:
            self.safety.record_response(500)
            raise RuntimeError(f"Network error communicating with target: {exc}") from exc
