import React, { useEffect, useState } from 'react';
import { RefreshCw, Search, Clock, ExternalLink } from 'lucide-react';
import { api } from '../api/client';

interface TopBarProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({ onRefresh, isRefreshing = false }) => {
  const [timeStr, setTimeStr] = useState<string>('');
  const [spend, setSpend] = useState<{ daily_spend_usd: number; daily_cap_usd: number } | null>(null);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toUTCString().slice(17, 25) + ' UTC');
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);

    api.getSpendSummary()
      .then((data) => setSpend(data))
      .catch(() => {});

    return () => clearInterval(timer);
  }, []);

  return (
    <header className="topbar">
      {/* Left: Breadcrumbs & Environment Tag */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '0.8rem' }}>
          <span style={{ color: 'var(--text-tertiary)' }}>Projects</span>
          <span style={{ color: 'var(--border-active)' }}>/</span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>shopops-prod</span>
        </div>

        <span className="badge badge-default" style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
          MCP Gateway :8000
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--emerald)' }}>
          <span className="pulse-dot"></span>
          <span style={{ fontWeight: 500 }}>System Healthy</span>
        </div>
      </div>

      {/* Center: Command Palette search input */}
      <div style={{ width: '320px' }}>
        <div className="search-input-wrapper">
          <Search size={14} className="search-input-icon" />
          <input
            type="text"
            placeholder="Search trace IDs, tools, or errors (⌘K)..."
            style={{ height: '30px', fontSize: '0.76rem', borderRadius: 'var(--radius-sm)' }}
          />
        </div>
      </div>

      {/* Right: LLM Budget, Clock, Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Daily LLM Budget */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.74rem',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-default)',
            padding: '4px 10px',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <span style={{ color: 'var(--text-tertiary)' }}>Daily LLM:</span>
          <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
            ${spend ? spend.daily_spend_usd.toFixed(2) : '0.02'}
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            / ${spend ? spend.daily_cap_usd.toFixed(0) : '50'}
          </span>
        </div>

        {/* UTC Clock */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.74rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          <Clock size={13} />
          <span>{timeStr || '12:00:00 UTC'}</span>
        </div>

        {/* Refresh button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="btn btn-secondary btn-sm"
            style={{ width: '28px', height: '28px', padding: 0 }}
            title="Refresh telemetry"
          >
            <RefreshCw size={13} className={isRefreshing ? 'animate-spin' : ''} />
          </button>
        )}

        {/* Link back to public website */}
        <a
          href="/"
          className="btn btn-secondary btn-sm"
          style={{ fontSize: '0.72rem', padding: '4px 9px', display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
          title="Return to Public Landing Page"
        >
          <span>Website</span>
        </a>

        {/* Swagger API Link */}
        <a
          href="http://127.0.0.1:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="btn btn-outline btn-sm"
          style={{ fontSize: '0.72rem', padding: '4px 8px' }}
        >
          <span>OpenAPI</span>
          <ExternalLink size={11} />
        </a>

        {/* Operator Profile */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            fontSize: '0.76rem',
            paddingLeft: '6px',
            borderLeft: '1px solid var(--border-default)',
          }}
        >
          <div
            style={{
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              backgroundColor: '#10b981',
              color: '#000000',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: '0.68rem',
            }}
          >
            AI
          </div>
          <span style={{ color: 'var(--text-secondary)', fontSize: '0.76rem' }}>
            engineer
          </span>
        </div>
      </div>
    </header>
  );
};
