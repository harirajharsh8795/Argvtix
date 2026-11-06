"""
Scout Runtime Egress Boundary Tests (WS-2).

Proves that:
1. HTTPChatAdapter validates target URL against signed ScopeConfig allowed_hosts and allowed_paths.
2. An out-of-scope target server receives ZERO requests in its access log.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from argvtix.scout.adapters.http import HTTPChatAdapter
from argvtix.scout.safety import ScoutSafetyViolationError
from argvtix.scout.scope import ScopeConfig, ScoutPermissionError, TargetTier


class RequestLoggingServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_log: list[str] = []


class LoggingHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.access_log.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"response": "out-of-scope mock reply"}')

    def log_message(self, format, *args):
        pass  # Quiet output during test run


@pytest.fixture
def unapproved_target_server():
    """Starts an unapproved local HTTP server that logs all incoming requests."""
    server = RequestLoggingServer(("127.0.0.1", 0), LoggingHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/api/v1/chat", server
    finally:
        server.shutdown()
        server.server_close()


def test_egress_refusal_and_zero_out_of_scope_network_requests(unapproved_target_server):
    """Proves that out-of-scope destination is blocked before dispatch and server receives 0 requests."""
    unapproved_url, server_instance = unapproved_target_server

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)

    # Scope only permits legitimate production staging host
    scope = ScopeConfig(
        scope_id="SCOPE-EGRESS-001",
        target_name="Authorized Internal Chatbot",
        target_url="http://app.argvtix.ai/chat",
        target_tier=TargetTier.T0_INTERNAL_SANDBOX,
        allowed_hosts=["app.argvtix.ai"],
        allowed_paths=["/chat"],
        operator_signature="ED25519-SIGNATURE-VERIFIED",
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=24),
    )

    adapter = HTTPChatAdapter(scope=scope, endpoint_url=unapproved_url)

    # Attempt to send message to unapproved host
    with pytest.raises(
        (ScoutPermissionError, ScoutSafetyViolationError), match="not in allowed_hosts"
    ):
        adapter.send_message("Test probe to unauthorized destination")

    # Critical Assertion: The unapproved server must have received ZERO requests
    assert len(server_instance.access_log) == 0, (
        f"Security violation: Out-of-scope server received {len(server_instance.access_log)} requests!"
    )
