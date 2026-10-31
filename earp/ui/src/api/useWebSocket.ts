import { useEffect, useRef, useState, useCallback } from 'react'

export type EventType =
  | 'guard.decision'
  | 'approval.requested'
  | 'approval.resolved'
  | 'watchdog.alert'
  | 'eval.complete'
  | 'benchmark.result'
  | 'trace.recorded'
  | 'system.notice'
  | 'system.pong'

export interface LiveEvent {
  event_type: EventType
  payload: Record<string, unknown>
  timestamp: number
  source: string
}

interface UseWebSocketOptions {
  url?: string
  maxEvents?: number
}

export function useWebSocket({ url, maxEvents = 100 }: UseWebSocketOptions = {}) {
  const WS_URL = url ?? `ws://${window.location.hostname}:8000/ws/events`
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pingInterval = useRef<ReturnType<typeof setInterval> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setError(null)
        // Send heartbeat every 25 seconds
        pingInterval.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping')
        }, 25_000)
      }

      ws.onmessage = (msg) => {
        try {
          const evt: LiveEvent = JSON.parse(msg.data)
          if (evt.event_type === 'system.pong') return
          setEvents((prev) => [evt, ...prev].slice(0, maxEvents))
        } catch {
          // ignore malformed frames
        }
      }

      ws.onerror = () => {
        setError('WebSocket connection error')
        setConnected(false)
      }

      ws.onclose = () => {
        setConnected(false)
        if (pingInterval.current) clearInterval(pingInterval.current)
        // Reconnect after 3 seconds
        setTimeout(connect, 3_000)
      }
    } catch (err) {
      setError(String(err))
    }
  }, [WS_URL, maxEvents])

  useEffect(() => {
    connect()
    return () => {
      if (pingInterval.current) clearInterval(pingInterval.current)
      wsRef.current?.close()
    }
  }, [connect])

  const clearEvents = () => setEvents([])

  return { events, connected, error, clearEvents }
}
