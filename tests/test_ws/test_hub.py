"""
Tests for ARGVTIX Real-Time WebSocket Hub and Router.
Verifies client lifecycle, typed event broadcast, and FastAPI endpoint integration.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from argvtix.gateway.app import app
from argvtix.ws.hub import ConnectionHub, Event, EventType, broadcast, get_hub


class TestEventSerialization:
    """Verifies typed Event JSON serialization."""

    def test_event_to_json(self):
        ev = Event(
            event_type=EventType.GUARD_DECISION,
            payload={"decision": "BLOCK", "reason": "High fraud risk"},
            source="guard-engine",
        )
        raw = ev.to_json()
        data = json.loads(raw)
        assert data["event_type"] == "guard.decision"
        assert data["payload"]["decision"] == "BLOCK"
        assert data["source"] == "guard-engine"
        assert "timestamp" in data


class TestConnectionHubLifecycle:
    """ConnectionHub connection management and broadcast delivery."""

    @pytest.mark.asyncio
    async def test_connect_welcomes_client(self):
        hub = ConnectionHub()
        mock_ws = AsyncMock()

        await hub.connect(mock_ws)
        assert hub.connected_count == 1
        mock_ws.accept.assert_awaited_once()
        mock_ws.send_text.assert_awaited_once()

        welcome_payload = json.loads(mock_ws.send_text.call_args[0][0])
        assert welcome_payload["event_type"] == "system.notice"
        assert "Connected to Argvtix" in welcome_payload["payload"]["message"]

    @pytest.mark.asyncio
    async def test_disconnect_client(self):
        hub = ConnectionHub()
        mock_ws = AsyncMock()

        await hub.connect(mock_ws)
        assert hub.connected_count == 1

        hub.disconnect(mock_ws)
        assert hub.connected_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_multiple_clients(self):
        hub = ConnectionHub()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await hub.connect(ws1)
        await hub.connect(ws2)
        assert hub.connected_count == 2

        # Reset send_text call counts from welcome events
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        event = Event(
            event_type=EventType.APPROVAL_REQUESTED,
            payload={"approval_id": "app_999", "amount": 20000.0},
        )
        await hub.broadcast(event)

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

        msg = json.loads(ws1.send_text.call_args[0][0])
        assert msg["event_type"] == "approval.requested"
        assert msg["payload"]["approval_id"] == "app_999"

    @pytest.mark.asyncio
    async def test_broadcast_drops_broken_client_gracefully(self):
        hub = ConnectionHub()
        healthy_ws = AsyncMock()
        failing_ws = AsyncMock()

        await hub.connect(healthy_ws)
        await hub.connect(failing_ws)
        assert hub.connected_count == 2

        # Break failing_ws after connection established
        failing_ws.send_text.side_effect = ConnectionResetError("Connection lost")
        healthy_ws.send_text.reset_mock()

        event = Event(
            event_type=EventType.WATCHDOG_ALERT,
            payload={"rule": "duplicate_refund"},
        )
        await hub.broadcast(event)

        # Healthy client received message
        healthy_ws.send_text.assert_awaited_once()
        # Failing client dropped from hub
        assert hub.connected_count == 1


class TestWebSocketRouterEndpoints:
    """FastAPI integration endpoints for WebSocket status and streaming."""

    def test_ws_status_endpoint(self):
        client = TestClient(app)
        res = client.get("/ws/status")
        assert res.status_code == 200
        data = res.json()
        assert "connected_clients" in data
        assert data["endpoint"] == "ws://host/ws/events"

    def test_ws_test_push_endpoint(self):
        client = TestClient(app)
        res = client.post("/ws/test?message=IntegrationTestPing")
        assert res.status_code == 200
        data = res.json()
        assert data["pushed"] is True
        assert data["message"] == "IntegrationTestPing"

    def test_ws_events_stream_and_ping_pong(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/events") as websocket:
            # First message should be the welcome notice
            welcome_raw = websocket.receive_text()
            welcome = json.loads(welcome_raw)
            assert welcome["event_type"] == "system.notice"

            # Send ping, expect system.pong
            websocket.send_text("ping")
            pong_raw = websocket.receive_text()
            pong = json.loads(pong_raw)
            assert pong["event_type"] == "system.pong"
