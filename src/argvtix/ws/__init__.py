"""
Real-Time WebSocket Broadcast Hub.

Pushes platform events (guard decisions, approval requests,
watchdog alerts, eval results) live to connected React clients.
"""
from argvtix.ws.hub import ConnectionHub, Event, EventType, broadcast

__all__ = ["ConnectionHub", "Event", "EventType", "broadcast"]
