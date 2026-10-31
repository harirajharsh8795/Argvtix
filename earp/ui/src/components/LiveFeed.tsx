import React, { useState } from 'react';
import { useWebSocket } from '../api/useWebSocket';
import {
  Terminal,
  Trash2,
  Pause,
  Play,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

const EVENT_TYPE_BADGES: Record<string, { label: string; color: string; bg: string; border: string }> = {
  'guard.decision': {
    label: 'GUARD.DECISION',
    color: 'var(--accent-danger)',
    bg: 'rgba(239, 68, 68, 0.12)',
    border: 'rgba(239, 68, 68, 0.25)',
  },
  'approval.requested': {
    label: 'APPROVAL.REQUESTED',
    color: 'var(--accent-warning)',
    bg: 'rgba(245, 158, 11, 0.12)',
    border: 'rgba(245, 158, 11, 0.25)',
  },
  'approval.resolved': {
    label: 'APPROVAL.RESOLVED',
    color: 'var(--accent-success)',
    bg: 'rgba(16, 185, 129, 0.12)',
    border: 'rgba(16, 185, 129, 0.25)',
  },
  'watchdog.alert': {
    label: 'WATCHDOG.ALERT',
    color: 'var(--accent-warning)',
    bg: 'rgba(245, 158, 11, 0.12)',
    border: 'rgba(245, 158, 11, 0.25)',
  },
  'eval.complete': {
    label: 'EVAL.COMPLETE',
    color: 'var(--accent-primary)',
    bg: 'rgba(99, 102, 241, 0.12)',
    border: 'rgba(99, 102, 241, 0.25)',
  },
  'benchmark.result': {
    label: 'BENCHMARK.RESULT',
    color: 'var(--accent-cyan)',
    bg: 'rgba(6, 182, 212, 0.12)',
    border: 'rgba(6, 182, 212, 0.25)',
  },
  'trace.recorded': {
    label: 'TRACE.RECORDED',
    color: 'var(--accent-primary)',
    bg: 'rgba(99, 102, 241, 0.12)',
    border: 'rgba(99, 102, 241, 0.25)',
  },
  'system.notice': {
    label: 'SYSTEM.NOTICE',
    color: 'var(--text-secondary)',
    bg: 'rgba(148, 163, 184, 0.1)',
    border: 'rgba(148, 163, 184, 0.2)',
  },
};

function formatTimestamp(ts: number): string {
  const date = new Date(ts * 1000);
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  const s = String(date.getSeconds()).padStart(2, '0');
  const ms = String(date.getMilliseconds()).padStart(3, '0');
  return `${h}:${m}:${s}.${ms}`;
}

interface LiveFeedProps {
  maxEvents?: number;
  height?: string;
}

export const LiveFeed: React.FC<LiveFeedProps> = ({ maxEvents = 100, height = '460px' }) => {
  const { events, connected, error, clearEvents } = useWebSocket({ maxEvents });
  const [filterType, setFilterType] = useState<string>('all');
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [expandedIndices, setExpandedIndices] = useState<Record<number, boolean>>({});

  const toggleExpand = (idx: number) => {
    setExpandedIndices((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const filteredEvents = events.filter((ev) => {
    if (filterType === 'all') return true;
    return ev.event_type.startsWith(filterType);
  });

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height,
        background: 'var(--bg-canvas)',
        border: '1px solid var(--border-default)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {/* Console Top Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '10px 14px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-default)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: connected ? 'var(--accent-success)' : 'var(--accent-danger)',
                boxShadow: connected ? '0 0 6px var(--accent-success)' : 'none',
              }}
            />
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-bright)', letterSpacing: '0.04em' }}>
              WEBSOCKET EVENT BUS
            </span>
          </div>

          <span
            className="badge"
            style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              background: connected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              color: connected ? 'var(--accent-success)' : 'var(--accent-danger)',
              border: `1px solid ${connected ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)'}`,
            }}
          >
            {connected ? 'CONNECTED (ws://127.0.0.1:8000/ws/events)' : error || 'DISCONNECTED'}
          </span>
        </div>

        {/* Toolbar Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {filteredEvents.length} events
          </span>

          <button
            onClick={() => setIsPaused(!isPaused)}
            className="btn btn-secondary btn-sm"
            style={{ padding: '3px 8px', fontSize: '0.72rem' }}
            title={isPaused ? 'Resume stream' : 'Pause stream'}
          >
            {isPaused ? <Play size={11} /> : <Pause size={11} />}
            <span>{isPaused ? 'Resume' : 'Pause'}</span>
          </button>

          <button
            onClick={clearEvents}
            className="btn btn-secondary btn-sm"
            style={{ padding: '3px 8px', fontSize: '0.72rem' }}
            title="Clear buffer"
          >
            <Trash2 size={11} />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Filter Chips Bar */}
      <div
        style={{
          display: 'flex',
          gap: '6px',
          padding: '6px 14px',
          background: 'rgba(255, 255, 255, 0.01)',
          borderBottom: '1px solid var(--border-default)',
          overflowX: 'auto',
          flexShrink: 0,
        }}
      >
        {['all', 'guard', 'approval', 'watchdog', 'trace'].map((type) => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            style={{
              background: filterType === type ? 'var(--bg-elevated)' : 'transparent',
              color: filterType === type ? 'var(--text-bright)' : 'var(--text-muted)',
              border: `1px solid ${filterType === type ? 'var(--border-strong)' : 'transparent'}`,
              borderRadius: 'var(--radius-sm)',
              padding: '2px 8px',
              fontSize: '0.7rem',
              cursor: 'pointer',
              textTransform: 'uppercase',
              fontFamily: 'var(--font-mono)',
              fontWeight: filterType === type ? 600 : 400,
            }}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Console Stream Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}
      >
        {filteredEvents.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-muted)',
              gap: '6px',
            }}
          >
            <Terminal size={22} style={{ opacity: 0.5 }} />
            <span style={{ fontSize: '0.8rem' }}>Listening for live telemetry frames…</span>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Events emitted by ActionGuard, Watchdog, or Tracing will stream here in real time.
            </span>
          </div>
        ) : (
          filteredEvents.map((ev, idx) => {
            const badge = EVENT_TYPE_BADGES[ev.event_type] || EVENT_TYPE_BADGES['system.notice'];
            const isExpanded = !!expandedIndices[idx];

            return (
              <div
                key={idx}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '6px 10px',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  {/* Timestamp */}
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                    {formatTimestamp(ev.timestamp)}
                  </span>

                  {/* Event Type Badge */}
                  <span
                    style={{
                      fontSize: '0.65rem',
                      fontWeight: 700,
                      padding: '1px 6px',
                      borderRadius: '4px',
                      background: badge.bg,
                      color: badge.color,
                      border: `1px solid ${badge.border}`,
                    }}
                  >
                    {badge.label}
                  </span>

                  {/* Source chip */}
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
                    [{ev.source || 'runtime'}]
                  </span>

                  {/* Payload Summary Preview */}
                  <span
                    style={{
                      color: 'var(--text-primary)',
                      flex: 1,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {typeof ev.payload === 'object'
                      ? JSON.stringify(ev.payload)
                      : String(ev.payload)}
                  </span>

                  {/* Toggle details */}
                  <button
                    onClick={() => toggleExpand(idx)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      padding: '2px',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                  >
                    {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>
                </div>

                {/* Expanded Details JSON */}
                {isExpanded && (
                  <pre
                    style={{
                      marginTop: '6px',
                      padding: '8px 10px',
                      background: 'var(--bg-canvas)',
                      border: '1px solid var(--border-default)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--accent-cyan)',
                      fontSize: '0.72rem',
                      lineHeight: 1.45,
                      overflowX: 'auto',
                      margin: '6px 0 0 0',
                    }}
                  >
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
