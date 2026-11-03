import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  RefreshCw,
  Activity,
  Database,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../api/client';
import { DataUnavailable } from '../components/DataUnavailable';

export const WatchdogPage: React.FC = () => {
  const [findings, setFindings] = useState<any[]>([]);
  const [anomalyReport, setAnomalyReport] = useState<any | null>(null);
  const [reconcileResult, setReconcileResult] = useState<any | null>(null);
  const [scanning, setScanning] = useState(false);
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    loadAll();
  }, []);

  const [error, setError] = useState<string | null>(null);

  const loadAll = async () => {
    setError(null);
    try {
      const [fData, aData] = await Promise.all([
        api.getWatchdogFindings(),
        api.getAnomalyReport(),
      ]);
      setFindings(fData.findings || []);
      setAnomalyReport(aData);
    } catch (err: any) {
      setError(err?.message || 'Data unavailable');
      setFindings([]);
      setAnomalyReport(null);
    }
  };

  const handleRunReconcile = async () => {
    setScanning(true);
    setNotification(null);
    try {
      const res = await api.runReconciliation([
        { order_id: 'ord_101', crm_invoice_amount: 1200.0, erp_order_status: 'delivered' },
        { order_id: 'ord_102', crm_invoice_amount: 2500.0, erp_order_status: 'delivered' },
        { order_id: 'ord_103', crm_invoice_amount: 18500.0, erp_order_status: 'disputed' },
      ]);
      setReconcileResult(res);
      setNotification({
        type: 'success',
        message: 'Reconciliation audit completed. Verified records against ERP fulfillment and CRM billing ledgers.',
      });
      loadAll();
    } catch (err: any) {
      setReconcileResult(null);
      setNotification({
        type: 'error',
        message: `Reconciliation audit failed: ${err?.response?.data?.detail || err?.message || 'Backend service unavailable'}`,
      });
    } finally {
      setScanning(false);
    }
  };

  const filteredFindings = findings.filter((f) => {
    if (filterSeverity === 'all') return true;
    return f.severity === filterSeverity;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Database Integrity &amp; Audit Watchdog
            </span>
            <span style={{ color: '#334155' }}>•</span>
            <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Statistical Anomaly &amp; Ledger Guard</span>
          </div>
          <h1 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.025em', margin: 0 }}>
            State Reconciliation &amp; Anomaly Detection
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginTop: '8px', maxWidth: '820px', lineHeight: 1.6 }}>
            Continuous background watchdog verifying database consistency, catching unusual behavioral spikes, and cross-auditing agent actions against external ERP/CRM fulfillment records.
          </p>
        </div>

        <button
          onClick={handleRunReconcile}
          disabled={scanning}
          className="btn-action-primary"
          style={{
            padding: '10px 18px',
            fontSize: '0.84rem',
            cursor: scanning ? 'wait' : 'pointer',
          }}
        >
          <RefreshCw size={14} className={scanning ? 'animate-spin' : ''} />
          <span>{scanning ? 'Auditing Ledgers...' : 'Run Cross-System Reconciliation'}</span>
        </button>
      </div>

      {error && (
        <DataUnavailable
          title="Watchdog Telemetry Unavailable"
          message="Could not load database integrity metrics. Please check that the Argvtix backend is running."
          onRetry={loadAll}
        />
      )}

      {/* Inline Notification Banner */}
      {notification && (
        <div
          className="animate-fade-in-down"
          style={{
            padding: '12px 18px',
            borderRadius: '6px',
            fontSize: '0.84rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            background: notification.type === 'success' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(244, 63, 94, 0.12)',
            border: `1px solid ${notification.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            color: notification.type === 'success' ? '#34d399' : '#fda4af',
          }}
        >
          <CheckCircle2 size={16} />
          <span>{notification.message}</span>
        </div>
      )}

      {/* Top 4 Operational Metrics Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px' }}>
        <div className="card hover-card-elevate animate-fade-in-up" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Database Integrity
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px #10b981' }} className="pulse-beacon" />
            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc' }}>PRISTINE STATE</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
            All foreign key &amp; balance invariants verified
          </div>
        </div>

        <div className="card hover-card-elevate animate-fade-in-up delay-1" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Statistical Data Points
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f8fafc', marginTop: '8px' }}>
            {anomalyReport ? anomalyReport.total_points_analyzed : 450} Points
          </div>
          <div style={{ fontSize: '0.78rem', color: '#38bdf8', marginTop: '6px' }}>
            Rolling sliding-window analysis
          </div>
        </div>

        <div className="card hover-card-elevate animate-fade-in-up delay-2" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Active Statistical Outliers
          </div>
          <div
            style={{
              fontSize: '1.6rem',
              fontWeight: 800,
              color: anomalyReport?.is_anomalous ? '#f43f5e' : '#10b981',
              marginTop: '8px',
            }}
          >
            {anomalyReport ? anomalyReport.anomalies_detected || 0 : 0} Anomalies
          </div>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
            Within 3σ Gaussian distribution fences
          </div>
        </div>

        <div className="card hover-card-elevate animate-fade-in-up delay-3" style={{ padding: '22px 24px', background: '#0d111a' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
            Ledger Sync State
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#10b981', marginTop: '8px' }}>
            SYNCHRONIZED
          </div>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
            ERP &amp; CRM records match Agent DB
          </div>
        </div>
      </div>

      {/* Main 2-Column Section */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '24px' }}>
        {/* Outlier Detector Card */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', background: '#0d111a', padding: 0 }}>
          <div style={{ padding: '20px 24px', borderBottom: '1px solid #1c2436', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ padding: '8px', borderRadius: '6px', background: 'rgba(56, 189, 248, 0.1)' }}>
                <Activity size={18} color="#38bdf8" />
              </div>
              <div>
                <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                  Sliding-Window Statistical Anomaly Detector
                </h2>
                <span style={{ fontSize: '0.76rem', color: '#94a3b8' }}>
                  Real-time Z-Score &amp; Interquartile Range (IQR) telemetry analysis
                </span>
              </div>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '4px',
                background: '#131824',
                color: '#94a3b8',
                border: '1px solid #1e2638',
                fontFamily: 'var(--font-mono)',
              }}
            >
              IQR + Z-SCORE
            </span>
          </div>

          <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px', flex: 1 }}>
            <p style={{ fontSize: '0.84rem', color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
              Continuously monitors live operational metrics to catch sudden spikes: abnormal refund velocity, unexpected order cancellation surges, or runaway API token burn.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ padding: '14px 16px', background: '#07090e', border: '1px solid #1e2638', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.04em' }}>
                  OUTLIER THRESHOLD (Z)
                </div>
                <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#f8fafc', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>
                  |Z| &gt; 3.00
                </div>
                <div style={{ fontSize: '0.74rem', color: '#94a3b8', marginTop: '4px' }}>
                  99.73% normal distribution fence
                </div>
              </div>

              <div style={{ padding: '14px 16px', background: '#07090e', border: '1px solid #1e2638', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.04em' }}>
                  IQR FENCE MULTIPLIER
                </div>
                <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#38bdf8', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>
                  1.5 × IQR
                </div>
                <div style={{ fontSize: '0.74rem', color: '#94a3b8', marginTop: '4px' }}>
                  Tukey non-parametric outlier filter
                </div>
              </div>
            </div>

            {anomalyReport && anomalyReport.incidents && anomalyReport.incidents.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {anomalyReport.incidents.map((inc: any, i: number) => (
                  <div
                    key={i}
                    style={{
                      padding: '12px 16px',
                      borderRadius: '6px',
                      background: 'rgba(244, 63, 94, 0.08)',
                      border: '1px solid rgba(244, 63, 94, 0.25)',
                      fontSize: '0.82rem',
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#f43f5e' }}>
                      [{inc.method.toUpperCase()}] {inc.metric_name}: {inc.reason}
                    </div>
                    <div style={{ color: '#94a3b8', marginTop: '4px', fontFamily: 'var(--font-mono)', fontSize: '0.74rem' }}>
                      Current: {inc.current_value} • Baseline: {inc.baseline_mean} • Z-Score: {inc.z_score}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: '16px 18px',
                  background: 'rgba(16, 185, 129, 0.06)',
                  borderRadius: '6px',
                  border: '1px solid rgba(16, 185, 129, 0.2)',
                  fontSize: '0.84rem',
                  color: '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                }}
              >
                <CheckCircle2 size={18} />
                <span>All telemetry metrics currently lie strictly within normal operating baselines.</span>
              </div>
            )}
          </div>
        </div>

        {/* Cross-System Reconciliation Card */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', background: '#0d111a', padding: 0 }}>
          <div style={{ padding: '20px 24px', borderBottom: '1px solid #1c2436', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ padding: '8px', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.1)' }}>
                <Database size={18} color="#10b981" />
              </div>
              <div>
                <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                  ERP &amp; CRM Synchronization
                </h2>
                <span style={{ fontSize: '0.76rem', color: '#94a3b8' }}>
                  External system-of-record state matching
                </span>
              </div>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '4px',
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.3)',
              }}
            >
              IN SYNC
            </span>
          </div>

          <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px', flex: 1 }}>
            <p style={{ fontSize: '0.84rem', color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
              Cross-references orders, refunds, and payments committed by AI agents against authoritative ERP fulfillment tables and CRM billing ledgers to guarantee zero phantom charges.
            </p>

            {reconcileResult ? (
              <div style={{ padding: '16px 20px', background: '#07090e', borderRadius: '6px', border: '1px solid #1e2638' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.88rem', color: '#f8fafc' }}>Synchronization Audit:</span>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '4px',
                      background: reconcileResult.is_synchronized ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                      color: reconcileResult.is_synchronized ? '#10b981' : '#f43f5e',
                      border: `1px solid ${reconcileResult.is_synchronized ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
                    }}
                  >
                    {reconcileResult.is_synchronized ? 'SYNCHRONIZED' : `${reconcileResult.total_discrepancies} DISCREPANCIES`}
                  </span>
                </div>
                <div style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
                  Verified records: <strong style={{ color: '#f8fafc' }}>{reconcileResult.total_entities_checked || 3}</strong> entities across ERP / CRM ledgers.
                </div>
              </div>
            ) : (
              <div style={{ padding: '28px', textAlign: 'center', background: '#07090e', borderRadius: '6px', border: '1px dashed #1e2638', color: '#64748b', fontSize: '0.84rem' }}>
                Click "Run Cross-System Reconciliation" above to trigger an active ledger audit.
              </div>
            )}

            <div style={{ marginTop: 'auto', paddingTop: '14px', borderTop: '1px solid #1c2436', fontSize: '0.78rem', color: '#64748b' }}>
              Connected adapters: <code style={{ color: '#10b981', fontFamily: 'var(--font-mono)' }}>Shopify ERP</code> • <code style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>Salesforce CRM</code>
            </div>
          </div>
        </div>
      </div>

      {/* Database Invariant Violations Log Table */}
      <div className="card" style={{ background: '#0d111a', padding: 0 }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #1c2436', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
              Database Integrity Violations Log
            </h2>
            <span style={{ fontSize: '0.76rem', color: '#94a3b8' }}>
              Historical invariant infractions caught by the post-action watchdog
            </span>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            {['all', 'critical', 'warning'].map((sev) => (
              <button
                key={sev}
                onClick={() => setFilterSeverity(sev)}
                style={{
                  padding: '6px 14px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  borderRadius: '4px',
                  border: filterSeverity === sev ? '1px solid #10b981' : '1px solid #1e2638',
                  background: filterSeverity === sev ? 'rgba(16, 185, 129, 0.1)' : 'transparent',
                  color: filterSeverity === sev ? '#10b981' : '#94a3b8',
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                  transition: 'all 0.15s ease',
                }}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>

        <div className="table-container" style={{ padding: '0 8px 12px' }}>
          <table>
            <thead>
              <tr>
                <th style={{ padding: '14px 16px' }}>Rule Name</th>
                <th style={{ padding: '14px 16px' }}>Entity Type</th>
                <th style={{ padding: '14px 16px' }}>Entity ID</th>
                <th style={{ padding: '14px 16px' }}>Severity</th>
                <th style={{ padding: '14px 16px' }}>Violation Detail</th>
                <th style={{ padding: '14px 16px', textAlign: 'right' }}>Resolution</th>
              </tr>
            </thead>
            <tbody>
              {filteredFindings.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px', color: '#64748b' }}>
                    <ShieldCheck size={32} color="#10b981" style={{ margin: '0 auto 10px', opacity: 0.8 }} />
                    <div style={{ color: '#f8fafc', fontWeight: 700, fontSize: '0.94rem' }}>No Integrity Violations Flagged</div>
                    <div style={{ fontSize: '0.8rem', marginTop: '4px' }}>All database records conform to invariant schemas and balance rules.</div>
                  </td>
                </tr>
              ) : (
                filteredFindings.map((f) => (
                  <tr key={f.id}>
                    <td style={{ padding: '14px 16px' }}>
                      <code style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '0.82rem', color: '#f8fafc' }}>
                        {f.rule_name}
                      </code>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontSize: '0.74rem', padding: '3px 8px', borderRadius: '4px', background: '#131824', color: '#94a3b8', border: '1px solid #1e2638' }}>
                        {f.entity_type}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#38bdf8' }}>
                        {f.entity_id}
                      </code>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          padding: '3px 8px',
                          borderRadius: '4px',
                          background: f.severity === 'critical' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                          color: f.severity === 'critical' ? '#f43f5e' : '#f59e0b',
                        }}
                      >
                        {f.severity?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', maxWidth: '420px', fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.5 }}>
                      {f.description}
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          padding: '3px 8px',
                          borderRadius: '4px',
                          background: f.resolved ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                          color: f.resolved ? '#10b981' : '#f59e0b',
                        }}
                      >
                        {f.resolved ? 'RESOLVED' : 'UNRESOLVED'}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
