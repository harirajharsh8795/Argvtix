"""
Real-Time WebSocket Broadcast Hub.

Manages all connected WebSocket clients and pushes typed events
(Guard decisions, approval requests, Watchdog alerts, Eval results)
to every subscriber in real time.

Design:
  - Single hub instance per server process (singleton via module-level var)
  - Async broadcast using asyncio.gather (non-blocking per client)
  - Typed event schema so the React dashboard can route by event_type
  - Automatic cleanup on client disconnect
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from weakref import WeakSet


# ---------------------------------------------------------------------------
# Event schema
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    GUARD_DECISION     = "guard.decision"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_RESOLVED  = "approval.resolved"
    WATCHDOG_ALERT     = "watchdog.alert"
    EVAL_COMPLETE      = "eval.complete"
    BENCHMARK_RESULT   = "benchmark.result"
    TRACE_RECORDED     = "trace.recorded"
    SYSTEM_NOTICE      = "system.notice"


@dataclass
class Event:
    """Typed platform event pushed over WebSocket."""
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "earp"

    def to_json(self) -> str:
        d = {
            "event_type": self.event_type.value,
            "payload":    self.payload,
            "timestamp":  self.timestamp,
            "source":     self.source,
        }
        return json.dumps(d)


# ---------------------------------------------------------------------------
# Connection Hub
# ---------------------------------------------------------------------------

class ConnectionHub:
    """
    Thread-safe async broadcast hub for WebSocket connections.

    Usage (inside FastAPI WebSocket endpoint):
        hub = get_hub()
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()   # keep alive
        except:
            hub.disconnect(ws)

    To push an event from anywhere in the app:
        await hub.broadcast(Event(EventType.GUARD_DECISION, {...}))
    """

    def __init__(self) -> None:
        # Use a plain list; WeakSet not suitable for WebSocket objects
        self._clients: list[Any] = []
        self._lock = asyncio.Lock()

    @property
    def connected_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: Any) -> None:
        """Accept and register a new WebSocket client."""
        await websocket.accept()
        async with self._lock:
            self._clients.append(websocket)

        # Send welcome event
        welcome = Event(
            event_type=EventType.SYSTEM_NOTICE,
            payload={
                "message": "Connected to Proofline EARP real-time feed.",
                "clients": self.connected_count,
            },
        )
        await self._send_one(websocket, welcome)

    def disconnect(self, websocket: Any) -> None:
        """Remove a WebSocket client (called on disconnect/error)."""
        try:
            self._clients.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, event: Event) -> None:
        """Push an event to all connected clients; drop dead connections."""
        if not self._clients:
            return

        payload = event.to_json()
        dead: list[Any] = []

        tasks = [self._send_raw(ws, payload, dead) for ws in list(self._clients)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Clean up dead connections
        async with self._lock:
            for ws in dead:
                try:
                    self._clients.remove(ws)
                except ValueError:
                    pass

    async def _send_one(self, websocket: Any, event: Event) -> None:
        try:
            await websocket.send_text(event.to_json())
        except Exception:
            self.disconnect(websocket)

    async def _send_raw(self, websocket: Any, payload: str, dead: list) -> None:
        try:
            await websocket.send_text(payload)
        except Exception:
            dead.append(websocket)


# ---------------------------------------------------------------------------
# Module-level singleton + helper
# ---------------------------------------------------------------------------

_hub: ConnectionHub | None = None


def get_hub() -> ConnectionHub:
    """Return the global hub (lazy-init)."""
    global _hub
    if _hub is None:
        _hub = ConnectionHub()
    return _hub


async def broadcast(event_type: EventType, payload: dict[str, Any], source: str = "earp") -> None:
    """
    Convenience function to fire-and-forget an event to all WS clients.

    Usage:
        from earp.ws.hub import broadcast, EventType
        await broadcast(EventType.GUARD_DECISION, {"decision": "BLOCK", ...})
    """
    hub = get_hub()
    event = Event(event_type=event_type, payload=payload, source=source)
    await hub.broadcast(event)
