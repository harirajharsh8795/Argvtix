import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  ShieldCheck,
  CheckCircle2,
  Eye,
  ShieldAlert,
  BarChart2,
  ChevronDown,
  Terminal,
  Server,
  ArrowLeft,
} from 'lucide-react';
import { ArgvtixLogo } from './ArgvtixLogo';

interface SidebarProps {
  pendingApprovalsCount?: number;
  anomalyCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  pendingApprovalsCount = 0,
  anomalyCount = 0,
}) => {
  const sections = [
    {
      title: 'OBSERVABILITY',
      items: [
        {
          to: '/overview',
          label: 'Overview',
          icon: LayoutDashboard,
          badge: null,
        },
        {
          to: '/traces',
          label: 'Trace Explorer',
          icon: Activity,
          badge: 'Live',
          badgeColor: 'badge-default',
        },
      ],
    },
    {
      title: 'BOUNDARY ENFORCEMENT',
      items: [
        {
          to: '/guard',
          label: 'Guardrails & Approvals',
          icon: ShieldCheck,
          badge: pendingApprovalsCount > 0 ? `${pendingApprovalsCount}` : null,
          badgeColor: 'badge-warning',
        },
      ],
    },
    {
      title: 'RELIABILITY & EVALS',
      items: [
        {
          to: '/evals',
          label: 'Claim Verifier',
          icon: CheckCircle2,
          badge: 'pass^k',
          badgeColor: 'badge-slate',
        },
        {
          to: '/watchdog',
          label: 'Data Watchdog',
          icon: Eye,
          badge: anomalyCount > 0 ? `${anomalyCount}` : null,
          badgeColor: 'badge-danger',
        },
        {
          to: '/benchmark',
          label: 'Model Benchmarks',
          icon: BarChart2,
          badge: 'WS Stream',
          badgeColor: 'badge-cyan',
        },
      ],
    },
    {
      title: 'SECURITY & GOVERNANCE',
      items: [
        {
          to: '/security',
          label: 'Red Team & DLP',
          icon: ShieldAlert,
          badge: '40 Attk',
          badgeColor: 'badge-blue',
        },
      ],
    },
  ];

  return (
    <aside className="sidebar">
      {/* Workspace Switcher / Logo (Links to Landing Page) */}
      <Link
        id="sidebar-logo-link"
        to="/"
        title="Return to Public Website / Landing Page"
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid var(--border-default)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          textDecoration: 'none',
          background: 'rgba(255, 255, 255, 0.02)',
          transition: 'background 0.15s ease',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(16, 185, 129, 0.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)')}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ArgvtixLogo size={28} showBadge={false} />
          <div>
            <div style={{ fontSize: '0.68rem', color: '#10b981', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
              shopops-prod
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span className="badge badge-success" style={{ fontSize: '0.62rem', padding: '1px 5px' }}>LIVE</span>
          <ChevronDown size={14} color="var(--text-tertiary)" />
        </div>
      </Link>

      {/* Navigation Sections */}
      <nav style={{ padding: '16px 10px', flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {sections.map((sec) => (
          <div key={sec.title}>
            <div
              style={{
                fontSize: '0.66rem',
                fontWeight: 600,
                color: 'var(--text-muted)',
                letterSpacing: '0.08em',
                padding: '0 8px 6px',
              }}
            >
              {sec.title}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {sec.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    style={({ isActive }) => ({
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '7px 10px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.8rem',
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? '#fff' : 'var(--text-secondary)',
                      backgroundColor: isActive ? 'var(--bg-surface-elevated)' : 'transparent',
                      border: isActive ? '1px solid var(--border-default)' : '1px solid transparent',
                      borderLeft: isActive ? '2px solid #10b981' : '2px solid transparent',
                      textDecoration: 'none',
                      transition: 'all 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
                    })}
                    className="hover-card-elevate"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </div>

                    {item.badge && (
                      <span className={`badge ${item.badgeColor || 'badge-default'}`} style={{ fontSize: '0.64rem', padding: '1px 5px' }}>
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* System Status Footer */}
      <div
        style={{
          padding: '12px 14px',
          borderTop: '1px solid var(--border-default)',
          backgroundColor: 'rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          fontSize: '0.72rem',
          color: 'var(--text-tertiary)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Server size={12} /> Tool Gateway:
          </span>
          <span style={{ color: 'var(--emerald)', fontFamily: 'var(--font-mono)' }}>MCP Active :8000</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Terminal size={12} /> Test Suite:
          </span>
          <span style={{ color: '#10b981', fontFamily: 'var(--font-mono)' }}>328/328 Green</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '6px', borderTop: '1px solid var(--border-default)' }}>
          <Link
            to="/"
            style={{
              color: '#10b981',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '0.74rem',
              fontWeight: 600,
            }}
          >
            <ArrowLeft size={12} />
            <span>Back to Public Website</span>
          </Link>
          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>v1.2.0-prod</span>
        </div>
      </div>
    </aside>
  );
};
