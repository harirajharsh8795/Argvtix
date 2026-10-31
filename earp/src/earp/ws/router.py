"""
FastAPI WebSocket Router.

Mounts the real-time event feed at /ws/events.
The React dashboard connects here via native browser WebSocket API.

Also exposes:
  GET /ws/status  — number of currently connected clients
  POST /ws/test   — push a test event (dev/debug only)
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from earp.ws.hub import Event, EventType, broadcast, get_hub

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/events")
async def websocket_events(websocket: WebSocket) -> None:
    """
    Primary real-time event stream endpoint.

    React dashboard connects: new WebSocket("ws://localhost:8000/ws/events")
    """
    hub = get_hub()
    await hub.connect(websocket)
    try:
        while True:
            # Keep the connection alive; clients may send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"event_type":"system.pong"}')
    except WebSocketDisconnect:
        hub.disconnect(websocket)
    except Exception:
        hub.disconnect(websocket)


@router.get("/status")
async def ws_status() -> JSONResponse:
    """Return count of active WebSocket connections."""
    hub = get_hub()
    return JSONResponse({
        "connected_clients": hub.connected_count,
        "endpoint": "ws://host/ws/events",
    })


@router.post("/test")
async def push_test_event(event_type: str = "system.notice", message: str = "Test event") -> JSONResponse:
    """Push a test event to all connected clients (dev only). Disabled in production."""
    import os
    env = os.getenv("ENVIRONMENT", os.getenv("PROOFLINE_ENV", "development")).lower()
    if env in ("production", "prod", "staging"):
        return JSONResponse(
            status_code=403,
            content={"detail": "WebSocket test endpoint is disabled in production."},
        )

    await broadcast(
        event_type=EventType.SYSTEM_NOTICE,
        payload={"message": message, "test": True},
        source="dev-test",
    )
    hub = get_hub()
    return JSONResponse({
        "pushed": True,
        "clients_notified": hub.connected_count,
        "message": message,
    })
