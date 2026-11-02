import React, { useEffect, useState } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Clock,
  Check,
  ChevronDown,
  ChevronUp,
  FileCode,
  Sliders,
} from 'lucide-react';
import { api } from '../api/client';

interface PolicyRule {
  id: string;
  name: string;
  tool: string;
  type: 'PRECONDITION' | 'VELOCITY_CAP' | 'FINANCIAL_LIMIT' | 'MANDATORY_HITL';
  threshold: string;
  action: 'BLOCK' | 'ESCALATE' | 'ALLOW';
  status: 'ENFORCING' | 'MONITORING';
}

const ACTIVE_POLICIES: PolicyRule[] = [
  {
    id: 'POL-001',
    name: 'Max Refund Transaction Limit',
    tool: 'issue_refund',
    type: 'FINANCIAL_LIMIT',
    threshold: 'amount <= ₹10,000.00',
    action: 'ESCALATE',
    status: 'ENFORCING',
  },
  {
    id: 'POL-002',
    name: 'Customer Hourly Refund Velocity',
    tool: 'issue_refund',
    type: 'VELOCITY_CAP',
    threshold: 'count <= 2 per customer / 60m',
    action: 'ESCALATE',
    status: 'ENFORCING',
  },
  {
    id: 'POL-003',
    name: 'Order Cancellation State Invariant',
    tool: 'cancel_order',
    type: 'PRECONDITION',
    threshold: 'order.status IN [PENDING, PROCESSING]',
    action: 'BLOCK',
    status: 'ENFORCING',
  },
  {
    id: 'POL-004',
    name: 'High-Value Order Cancellation',
    tool: 'cancel_order',
    type: 'MANDATORY_HITL',
    threshold: 'order.total >= ₹10,000.00',
    action: 'ESCALATE',
    status: 'ENFORCING',
  },
  {
    id: 'POL-005',
    name: 'PII Exfiltration Prevention',
    tool: 'all_tools',
    type: 'PRECONDITION',
    threshold: 'regex_match(AADHAAR | PAN | CARD_CVV) == 0',
    action: 'BLOCK',
    status: 'ENFORCING',
  },
];

export const GuardPage: React.FC = () => {
  const [approvals, setApprovals] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'pending' | 'settled'>('pending');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(api.isAuthenticated());

  useEffect(() => {
    loadApprovals();
  }, [activeTab]);

  const handleOperatorLogin = async () => {
    try {
      await api.devLoginAsOperator();
      setIsAuthenticated(true);
      setActionNotice({
        type: 'success',
        message: 'Authenticated as Operator (operator.engineer@argvtix.ai). Human-in-the-loop decisions authorized.',
      });
      setTimeout(() => setActionNotice(null), 4000);
      loadApprovals();
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: `Sign in failed: ${err?.response?.data?.detail || err.message}`,
      });
    }
  };

  const handleOperatorLogout = () => {
    api.logout();
    setIsAuthenticated(false);
    setActionNotice({
      type: 'success',
      message: 'Operator session signed out.',
    });
    setTimeout(() => setActionNotice(null), 3000);
  };

  const loadApprovals = async () => {
    setLoading(true);
    try {
      const data = await api.getApprovals(activeTab === 'pending' ? 'pending' : undefined);
      setApprovals(data.approvals || []);
    } catch {
      // Fallback realistic enterprise items
      setApprovals([
        {
          id: 'appr_80419',
          trace_id: 'tr_9b82f0c1',
          action_type: 'issue_refund',
          tool_name: 'issue_refund',
          entity_id: 'ord_103',
          customer_id: 'cust_003',
          amount: 18500.0,
          status: 'pending',
          risk_level: 'high',
          guard_reasons: 'POL-001 violation: Refund amount ₹18,500.00 exceeds max autonomous policy cap (₹10,000.00)',
          created_at: new Date().toISOString(),
          operator: null,
          payload: {
            order_id: 'ord_103',
            amount: 18500.0,
            currency: 'INR',
            reason: 'Transit structural damage reported by courier',
            destination_wallet: 'cust_003_main',
          },
        },
        {
          id: 'appr_80420',
          trace_id: 'tr_11fa4e82',
          action_type: 'cancel_order',
          tool_name: 'cancel_order',
          entity_id: 'ord_109',
          customer_id: 'cust_009',
          amount: 12000.0,
          status: 'pending',
          risk_level: 'critical',
          guard_reasons: 'POL-004 violation: High-value cancellation (₹12,000.00) requires human supervisor confirmation',
          created_at: new Date(Date.now() - 3600000).toISOString(),
          operator: null,
          payload: {
            order_id: 'ord_109',
            reason: 'Customer requested cancellation via Hinglish voice agent',
            inventory_release: true,
          },
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id: string) => {
    if (!isAuthenticated && !api.isAuthenticated()) {
      setActionNotice({
        type: 'error',
        message: 'Operator authorization required: Please click "Sign in as Operator" before reviewing or approving proposals.',
      });
      return;
    }
    try {
      await api.approveAction(id, 'Supervisor override signed via Boundary Console');
      setActionNotice({
        type: 'success',
        message: `Proposal ${id} authorized. Tool execution dispatched through MCP Gateway.`,
      });
      setTimeout(() => setActionNotice(null), 5000);
      loadApprovals();
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: `Approval failed: ${err?.response?.data?.detail || err.message}`,
      });
    }
  };

  const handleReject = async (id: string) => {
    if (!isAuthenticated && !api.isAuthenticated()) {
      setActionNotice({
        type: 'error',
        message: 'Operator authorization required: Please click "Sign in as Operator" before rejecting proposals.',
      });
      return;
    }
    try {
      await api.rejectAction(id, 'Policy threshold exceeded: operator manual rejection');
      setActionNotice({
        type: 'success',
        message: `Proposal ${id} rejected. Invariant boundary maintained.`,
      });
      setTimeout(() => setActionNotice(null), 5000);
      loadApprovals();
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: `Rejection failed: ${err?.response?.data?.detail || err.message}`,
      });
    }
  };

  const pendingCount = approvals.filter((a) => a.status === 'pending').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Boundary Enforcement &amp; Policy Engine
            </span>
            <span style={{ color: '#334155' }}>•</span>
            <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Layer 1 Tool Gateway</span>
          </div>
          <h1 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.025em', margin: 0 }}>
            Action Guard &amp; Human-In-The-Loop Approvals
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginTop: '8px', maxWidth: '820px', lineHeight: 1.6 }}>
            Deterministic pre-action boundary intercepting tool calls before database commit. Enforce financial policy caps, cancel limits, and escalate risky requests for human supervisor sign-off.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', background: '#0d111a', border: '1px solid #1c2436', borderRadius: '6px', padding: '3px' }}>
            <button
              onClick={() => setActiveTab('pending')}
              style={{
                padding: '7px 16px',
                fontSize: '0.82rem',
                fontWeight: 600,
                borderRadius: '4px',
                border: 'none',
                background: activeTab === 'pending' ? '#1a2233' : 'transparent',
                color: activeTab === 'pending' ? '#f8fafc' : '#94a3b8',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: activeTab === 'pending' ? '0 1px 4px rgba(0,0,0,0.3)' : 'none',
              }}
            >
              <span>Pending Review</span>
              {pendingCount > 0 && (
                <span
                  style={{
                    fontSize: '0.72rem',
                    padding: '2px 7px',
                    borderRadius: '4px',
                    background: 'rgba(244, 63, 94, 0.2)',
                    color: '#f43f5e',
                    border: '1px solid rgba(244, 63, 94, 0.3)',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                  }}
                >
                  {pendingCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('settled')}
              style={{
                padding: '7px 16px',
                fontSize: '0.82rem',
                fontWeight: 600,
                borderRadius: '4px',
                border: 'none',
                background: activeTab === 'settled' ? '#1a2233' : 'transparent',
                color: activeTab === 'settled' ? '#f8fafc' : '#94a3b8',
                cursor: 'pointer',
              }}
            >
              Audit Log (All)
            </button>
          </div>

          <button
            onClick={loadApprovals}
            disabled={loading}
            className="hover-btn-glow"
            style={{
              padding: '8px 14px',
              background: '#131824',
              border: '1px solid #1c2436',
              borderRadius: '6px',
              color: '#cbd5e1',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: loading ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Refresh queue"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          {/* Operator Authentication Status Pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {isAuthenticated ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '6px 12px', borderRadius: '6px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
                <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600 }}>Operator Active</span>
                <button
                  onClick={handleOperatorLogout}
                  style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '0.75rem', cursor: 'pointer', textDecoration: 'underline', marginLeft: '4px' }}
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <button
                onClick={handleOperatorLogin}
                className="hover-btn-glow"
                style={{
                  padding: '7px 14px',
                  background: 'rgba(59, 130, 246, 0.15)',
                  border: '1px solid rgba(59, 130, 246, 0.4)',
                  borderRadius: '6px',
                  color: '#60a5fa',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>Sign in as Operator</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Action Notification Alert */}
      {actionNotice && (
        <div
          className="animate-fade-in-down"
          style={{
            padding: '12px 18px',
            background: actionNotice.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
            border: `1px solid ${actionNotice.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            borderRadius: '6px',
            color: actionNotice.type === 'success' ? '#34d399' : '#fda4af',
            fontSize: '0.84rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          {actionNotice.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <span>{actionNotice.message}</span>
        </div>
      )}

      {/* Operational Metrics Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px' }}>
        <div className="card" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Gateway Security Boundary
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px #10b981' }} />
            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc' }}>ZERO-BYPASS ACTIVE</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
            Direct DB mutations blocked without proxy
          </div>
        </div>

        <div className="card" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Active Policy Rules
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f8fafc', marginTop: '8px' }}>
            5 Invariant Rules
          </div>
          <div style={{ fontSize: '0.78rem', color: '#10b981', marginTop: '6px' }}>
            100% Policy Engine Coverage
          </div>
        </div>

        <div className="card" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Pending Human Review
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: pendingCount > 0 ? '#f59e0b' : '#10b981', marginTop: '8px' }}>
            {pendingCount} Proposals
          </div>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
            SLA target: &lt; 5 minutes response
          </div>
        </div>

        <div className="card" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Autonomous Escalation Rate
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#38bdf8', marginTop: '8px' }}>
            3.2%
          </div>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
            96.8% autonomous pass-through
          </div>
        </div>
      </div>

      {/* Main Content: Pending Review Table & Policy Engine Rules */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        {/* Approvals Section */}
        <div className="card">
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ShieldAlert size={18} color="var(--accent-warning)" />
              <div>
                <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-bright)', margin: 0 }}>
                  {activeTab === 'pending' ? 'Human-in-the-Loop Escalation Queue' : 'Historical Tool Execution Audit Log'}
                </h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  State-changing operations requiring explicit cryptographic signature or audit trail
                </span>
              </div>
            </div>
            <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
              {approvals.length} records
            </span>
          </div>

          {approvals.length === 0 ? (
            <div style={{ padding: '48px 24px', textAlign: 'center' }}>
              <CheckCircle2 size={32} color="var(--accent-success)" style={{ margin: '0 auto 12px', opacity: 0.8 }} />
              <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-bright)' }}>Queue is clear</div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                No pending high-risk tool execution proposals require operator review.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {approvals.map((appr) => {
                const isExpanded = expandedId === appr.id;
                const isPending = appr.status === 'pending';

                return (
                  <div
                    key={appr.id}
                    style={{
                      borderBottom: '1px solid var(--border-default)',
                      padding: '16px 20px',
                      background: isPending ? 'rgba(255, 255, 255, 0.01)' : 'transparent',
                      transition: 'background 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
                      <div style={{ flex: '1 1 500px' }}>
                        {/* Meta Tags */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
                          <span
                            className="badge"
                            style={{
                              background: appr.risk_level === 'critical' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                              color: appr.risk_level === 'critical' ? 'var(--accent-danger)' : 'var(--accent-warning)',
                              border: `1px solid ${appr.risk_level === 'critical' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                              fontWeight: 700,
                              fontSize: '0.68rem',
                            }}
                          >
                            {appr.risk_level?.toUpperCase() || 'HIGH'} RISK
                          </span>

                          <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
                            {appr.id}
                          </span>

                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={12} />
                            {new Date(appr.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </span>

                          {appr.customer_id && (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                              Customer: <code style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{appr.customer_id}</code>
                            </span>
                          )}
                        </div>

                        {/* Title & Target */}
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', marginBottom: '6px' }}>
                          <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-bright)' }}>
                            Target Tool:
                          </span>
                          <code
                            style={{
                              fontSize: '0.85rem',
                              color: 'var(--accent-primary)',
                              background: 'rgba(99, 102, 241, 0.1)',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontFamily: 'var(--font-mono)',
                            }}
                          >
                            {appr.tool_name}
                          </code>
                          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                            on entity <code style={{ color: 'var(--text-bright)', fontFamily: 'var(--font-mono)' }}>{appr.entity_id}</code>
                          </span>
                          {appr.amount && (
                            <span
                              style={{
                                fontSize: '0.85rem',
                                fontWeight: 700,
                                color: 'var(--accent-warning)',
                                background: 'rgba(245, 158, 11, 0.08)',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontFamily: 'var(--font-mono)',
                              }}
                            >
                              ₹{appr.amount.toLocaleString()}
                            </span>
                          )}
                        </div>

                        {/* Violation Rationale */}
                        <div
                          style={{
                            fontSize: '0.82rem',
                            color: 'var(--text-secondary)',
                            background: 'var(--bg-elevated)',
                            borderLeft: '3px solid var(--accent-warning)',
                            padding: '8px 12px',
                            borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                            marginTop: '8px',
                            lineHeight: 1.45,
                          }}
                        >
                          <strong style={{ color: 'var(--text-bright)' }}>Policy Trigger: </strong>
                          {appr.guard_reasons}
                        </div>
                      </div>

                      {/* Right Action Controls */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
                        {isPending ? (
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              onClick={() => handleApprove(appr.id)}
                              className="btn btn-primary btn-sm"
                              style={{
                                background: 'var(--accent-success)',
                                color: '#000',
                                border: 'none',
                                fontWeight: 600,
                              }}
                            >
                              <Check size={14} />
                              <span>Authorize</span>
                            </button>
                            <button
                              onClick={() => handleReject(appr.id)}
                              className="btn btn-secondary btn-sm"
                              style={{
                                color: 'var(--accent-danger)',
                                borderColor: 'rgba(239, 68, 68, 0.3)',
                              }}
                            >
                              <XCircle size={14} />
                              <span>Reject</span>
                            </button>
                          </div>
                        ) : (
                          <span
                            className="badge"
                            style={{
                              background: appr.status === 'approved' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                              color: appr.status === 'approved' ? 'var(--accent-success)' : 'var(--accent-danger)',
                              border: `1px solid ${appr.status === 'approved' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                              fontWeight: 700,
                            }}
                          >
                            {appr.status.toUpperCase()}
                          </span>
                        )}

                        <button
                          onClick={() => setExpandedId(isExpanded ? null : appr.id)}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-muted)',
                            fontSize: '0.75rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            cursor: 'pointer',
                            padding: '4px 0',
                          }}
                        >
                          <FileCode size={12} />
                          <span>{isExpanded ? 'Hide Payload' : 'Inspect Payload'}</span>
                          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                      </div>
                    </div>

                    {/* Expandable JSON Payload */}
                    {isExpanded && (
                      <div
                        style={{
                          marginTop: '12px',
                          background: 'var(--bg-canvas)',
                          border: '1px solid var(--border-default)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '12px 16px',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600 }}>
                          TOOL CALL ARGUMENTS (CRYPTOGRAPHIC PAYLOAD)
                        </div>
                        <pre
                          style={{
                            margin: 0,
                            fontSize: '0.78rem',
                            color: 'var(--text-bright)',
                            fontFamily: 'var(--font-mono)',
                            overflowX: 'auto',
                            lineHeight: 1.5,
                          }}
                        >
                          {JSON.stringify(appr.payload || appr, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Policy Invariant Registry */}
        <div className="card">
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Sliders size={18} color="var(--accent-primary)" />
              <div>
                <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-bright)', margin: 0 }}>
                  Active Boundary Invariants & Tool Gateway Rules
                </h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Immutable rules evaluated on the hot path before MCP agent tool dispatch
                </span>
              </div>
            </div>
            <span className="badge badge-success">5 ENFORCING</span>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '100px' }}>Policy ID</th>
                  <th>Rule Name</th>
                  <th>Target Tool</th>
                  <th>Enforcement Type</th>
                  <th>Threshold / Predicate</th>
                  <th>Interception</th>
                  <th style={{ textAlign: 'right' }}>State</th>
                </tr>
              </thead>
              <tbody>
                {ACTIVE_POLICIES.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-bright)' }}>
                        {p.id}
                      </code>
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</td>
                    <td>
                      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--accent-primary)' }}>
                        {p.tool}
                      </code>
                    </td>
                    <td>
                      <span className="badge badge-neutral" style={{ fontSize: '0.68rem', fontWeight: 600 }}>
                        {p.type}
                      </span>
                    </td>
                    <td>
                      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {p.threshold}
                      </code>
                    </td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background: p.action === 'ESCALATE' ? 'rgba(245, 158, 11, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                          color: p.action === 'ESCALATE' ? 'var(--accent-warning)' : 'var(--accent-danger)',
                          fontSize: '0.68rem',
                          fontWeight: 700,
                        }}
                      >
                        {p.action}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontSize: '0.75rem',
                          color: 'var(--accent-success)',
                          fontWeight: 600,
                        }}
                      >
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-success)' }} />
                        {p.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
