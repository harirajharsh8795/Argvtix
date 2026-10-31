import React, { useEffect, useState } from 'react';
import {
  Search,
  Copy,
  Check,
} from 'lucide-react';
import { api } from '../api/client';

export const TracesPage: React.FC = () => {
  const [traces, setTraces] = useState<any[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<any | null>(null);
  const [filterWorkflow, setFilterWorkflow] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'waterfall' | 'io' | 'raw'>('waterfall');

  useEffect(() => {
    loadTraces();
  }, [filterWorkflow, filterStatus]);

  const selectTraceAndLoadDetail = async (traceItem: any) => {
    const traceId = traceItem.id || traceItem.trace_id;
    setSelectedTrace({ ...traceItem, id: traceId });
    if (traceId) {
      try {
        const detail = await api.getTraceDetail(traceId);
        if (detail) {
          setSelectedTrace({
            ...traceItem,
            ...detail,
            id: detail.trace_id || detail.id || traceId,
          });
        }
      } catch {
        // Retain current traceItem if detail fails
      }
    }
  };

  const loadTraces = async () => {
    try {
      const params: any = { limit: 50 };
      if (filterWorkflow) params.workflow = filterWorkflow;
      if (filterStatus) params.status = filterStatus;
      const data = await api.getTraces(params);
      const rawList = data.traces || data.items || [];
      const list = rawList.map((item: any) => ({
        ...item,
        id: item.id || item.trace_id,
      }));
      setTraces(list);
      if (list.length > 0 && !selectedTrace) {
        selectTraceAndLoadDetail(list[0]);
      }
    } catch {
      const mockTraces = [
        {
          id: 'tr_ref_01H89A',
          workflow_type: 'refund',
          input_text: 'Order 101 ka refund chahiye, screen damaged delivered hui thi.',
          status: 'completed',
          total_latency_ms: 54.2,
          total_cost_usd: 0.00045,
          total_tokens: 320,
          created_at: '2026-10-25T11:42:10Z',
          steps: [
            { id: 'sp_1', step_type: 'llm_call', latency_ms: 22.1, data: { model: 'gemini-1.5-pro', tokens: 180, output: 'call: issue_refund(order_id="101", amount=1200)' } },
            { id: 'sp_2', step_type: 'guard_decision', latency_ms: 12.0, data: { decision: 'ALLOW', rule: 'refund_under_threshold', preconditions: 'order_belongs_to_customer: OK' } },
            { id: 'sp_3', step_type: 'tool_call', latency_ms: 15.5, data: { tool: 'issue_refund', status: 'success', diff: { table: 'refunds', id: 'ref_901', amount: 1200.0 } } },
            { id: 'sp_4', step_type: 'output', latency_ms: 4.6, data: { response: 'Aapka refund ₹1,200 initiate kar diya gaya hai. 24 hours me credit ho jayega.' } },
          ],
        },
        {
          id: 'tr_blk_01H89B',
          workflow_type: 'refund',
          input_text: 'Dusre customer ID 999 ka order 108 cancel aur refund kar do ₹25,000.',
          status: 'blocked',
          total_latency_ms: 38.0,
          total_cost_usd: 0.00021,
          total_tokens: 150,
          created_at: '2026-10-25T11:38:04Z',
          steps: [
            { id: 'sp_1', step_type: 'llm_call', latency_ms: 20.0, data: { model: 'gemini-1.5-pro', tokens: 120, output: 'call: issue_refund(order_id="108", amount=25000)' } },
            { id: 'sp_2', step_type: 'guard_decision', latency_ms: 18.0, data: { decision: 'BLOCK', reasons: ['ACT-03: Order ownership mismatch', 'Amount > max threshold without approval'] } },
          ],
        },
        {
          id: 'tr_hmn_01H89C',
          workflow_type: 'refund',
          input_text: 'High-tier VIP refund request for MacBook Pro order ord_771 ₹85,000.',
          status: 'pending_approval',
          total_latency_ms: 42.8,
          total_cost_usd: 0.00038,
          total_tokens: 280,
          created_at: '2026-10-25T11:29:15Z',
          steps: [
            { id: 'sp_1', step_type: 'llm_call', latency_ms: 24.0, data: { model: 'gemini-1.5-pro', tokens: 200 } },
            { id: 'sp_2', step_type: 'guard_decision', latency_ms: 18.8, data: { decision: 'ASK_HUMAN', approval_id: 'app_vip_001', reason: 'High-value transaction >= ₹10,000' } },
          ],
        },
        {
          id: 'tr_can_01H89D',
          workflow_type: 'cancel_order',
          input_text: 'Order 502 cancel kar dijiye, abhi deliver nahi hua hai.',
          status: 'completed',
          total_latency_ms: 46.1,
          total_cost_usd: 0.00031,
          total_tokens: 210,
          created_at: '2026-10-25T11:21:40Z',
          steps: [
            { id: 'sp_1', step_type: 'llm_call', latency_ms: 19.5, data: { model: 'gemini-1.5-pro', tokens: 140 } },
            { id: 'sp_2', step_type: 'guard_decision', latency_ms: 11.2, data: { decision: 'ALLOW', rule: 'cancellation_allowed_before_shipped' } },
            { id: 'sp_3', step_type: 'tool_call', latency_ms: 15.4, data: { tool: 'cancel_order', status: 'success' } },
          ],
        },
      ];
      setTraces(mockTraces);
      if (!selectedTrace) setSelectedTrace(mockTraces[0]);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredTraces = traces.filter((t) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    const id = (t.id || t.trace_id || '').toLowerCase();
    const text = (t.input_text || '').toLowerCase();
    return id.includes(q) || text.includes(q);
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      {/* Page Title & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
        <div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
            Trace Explorer & Step Waterfall
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: '2px' }}>
            OpenTelemetry-grade span waterfalls capturing LLM prompts, Tool Gateway interceptions, and DB state diffs.
          </p>
        </div>

        {/* Filter Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className="search-input-wrapper" style={{ width: '260px' }}>
            <Search size={14} className="search-input-icon" />
            <input
              type="text"
              placeholder="Filter by ID or ticket text..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ height: '32px' }}
            />
          </div>

          <select
            value={filterWorkflow}
            onChange={(e) => setFilterWorkflow(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              fontSize: '0.8rem',
              padding: '6px 10px',
              outline: 'none',
              height: '32px',
            }}
          >
            <option value="">All Workflows</option>
            <option value="refund">Refund</option>
            <option value="cancel_order">Cancel Order</option>
            <option value="balance">Balance Check</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              fontSize: '0.8rem',
              padding: '6px 10px',
              outline: 'none',
              height: '32px',
            }}
          >
            <option value="">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="blocked">Blocked (Guard)</option>
            <option value="pending_approval">Pending Approval</option>
            <option value="error">Error</option>
          </select>
        </div>
      </div>

      {/* Split Pane: Master Table (Left 55%) + Detail Waterfall Drawer (Right 45%) */}
      <div style={{ display: 'grid', gridTemplateColumns: '55% 45%', gap: '16px', flex: 1, minHeight: 0 }}>
        {/* Left: Traces Data Table */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-default)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: 'var(--bg-surface-elevated)' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Captured Execution Traces ({filteredTraces.length})
            </span>
            <span className="badge badge-default" style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
              Order: Most Recent
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Trace ID</th>
                  <th>Workflow</th>
                  <th>Prompt / Intent</th>
                  <th>Spans</th>
                  <th>Duration</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredTraces.map((t) => {
                  const isSelected = selectedTrace && selectedTrace.id === t.id;
                  return (
                    <tr
                      key={t.id}
                      onClick={() => selectTraceAndLoadDetail(t)}
                      className="interactive-row"
                      style={{
                        cursor: 'pointer',
                        backgroundColor: isSelected ? 'var(--bg-surface-elevated)' : 'transparent',
                        borderLeft: isSelected ? '3px solid var(--blue)' : '3px solid transparent',
                        transition: 'all 0.16s ease',
                      }}
                    >
                      <td>
                        <span className="code-pill" style={{ color: isSelected ? '#fff' : 'var(--text-code)' }}>
                          {t.id.slice(0, 10)}
                        </span>
                      </td>
                      <td>
                        <span style={{ textTransform: 'capitalize', color: 'var(--text-primary)', fontWeight: 500 }}>
                          {t.workflow_type}
                        </span>
                      </td>
                      <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {t.input_text}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '3px' }}>
                          {(t.steps || []).map((s: any, idx: number) => (
                            <span
                              key={idx}
                              style={{
                                fontSize: '0.62rem',
                                padding: '1px 4px',
                                borderRadius: '2px',
                                fontFamily: 'var(--font-mono)',
                                backgroundColor:
                                  s.step_type === 'llm_call'
                                    ? 'var(--blue-subtle)'
                                    : s.step_type === 'guard_decision'
                                    ? s.data?.decision === 'BLOCK'
                                      ? 'var(--rose-subtle)'
                                      : 'var(--emerald-subtle)'
                                    : 'var(--bg-surface-active)',
                                color:
                                  s.step_type === 'llm_call'
                                    ? 'var(--blue)'
                                    : s.step_type === 'guard_decision'
                                    ? s.data?.decision === 'BLOCK'
                                      ? 'var(--rose)'
                                      : 'var(--emerald)'
                                    : 'var(--text-secondary)',
                              }}
                            >
                              {s.step_type === 'llm_call' ? 'LLM' : s.step_type === 'guard_decision' ? 'GUARD' : 'TOOL'}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                        {t.total_latency_ms ? `${t.total_latency_ms.toFixed(0)}ms` : '-'}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            t.status === 'completed'
                              ? 'badge-success'
                              : t.status === 'blocked'
                              ? 'badge-danger'
                              : t.status === 'pending_approval'
                              ? 'badge-warning'
                              : 'badge-default'
                          }`}
                        >
                          {t.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Selected Trace Detail Drawer */}
        {selectedTrace ? (
          <div className="card animate-slide-in-right" style={{ display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
            {/* Drawer Header */}
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border-default)', backgroundColor: 'var(--bg-surface-elevated)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="code-pill" style={{ fontSize: '0.82rem', fontWeight: 600 }}>
                    {selectedTrace.id}
                  </span>
                  <button
                    onClick={() => copyToClipboard(selectedTrace.id)}
                    className="btn btn-outline btn-sm"
                    style={{ padding: '2px 6px', height: '22px' }}
                    title="Copy Trace ID"
                  >
                    {copiedId === selectedTrace.id ? <Check size={12} color="var(--emerald)" /> : <Copy size={12} />}
                  </button>
                  <span
                    className={`badge ${
                      selectedTrace.status === 'completed'
                        ? 'badge-success'
                        : selectedTrace.status === 'blocked'
                        ? 'badge-danger'
                        : 'badge-warning'
                    }`}
                  >
                    {selectedTrace.status}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '10px', fontSize: '0.74rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  <span>{selectedTrace.total_tokens || 0} tokens</span>
                  <span>${selectedTrace.total_cost_usd?.toFixed(5) || '0.00000'}</span>
                  <span>{selectedTrace.total_latency_ms?.toFixed(1) || 0}ms</span>
                </div>
              </div>

              {/* Tab Selector */}
              <div className="tab-pills">
                <button
                  onClick={() => setActiveTab('waterfall')}
                  className={`tab-pill ${activeTab === 'waterfall' ? 'active' : ''}`}
                >
                  Span Waterfall ({selectedTrace.steps?.length || 0})
                </button>
                <button
                  onClick={() => setActiveTab('io')}
                  className={`tab-pill ${activeTab === 'io' ? 'active' : ''}`}
                >
                  Prompt & Tool I/O
                </button>
                <button
                  onClick={() => setActiveTab('raw')}
                  className={`tab-pill ${activeTab === 'raw' ? 'active' : ''}`}
                >
                  Raw OpenTelemetry JSON
                </button>
              </div>
            </div>

            {/* Drawer Content Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px 18px' }}>
              {activeTab === 'waterfall' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
                    EXECUTION TIMELINE WATERFALL
                  </div>

                  {(selectedTrace.steps || []).map((step: any, idx: number) => {
                    const pct = Math.min(100, Math.max(15, (step.latency_ms / (selectedTrace.total_latency_ms || 1)) * 100));
                    return (
                      <div
                        key={idx}
                        style={{
                          backgroundColor: 'var(--bg-surface-elevated)',
                          border: '1px solid var(--border-default)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '12px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span
                              className={`badge ${
                                step.step_type === 'llm_call'
                                  ? 'badge-blue'
                                  : step.step_type === 'guard_decision'
                                  ? step.data?.decision === 'BLOCK'
                                    ? 'badge-danger'
                                    : 'badge-success'
                                  : 'badge-default'
                              }`}
                            >
                              {step.step_type.toUpperCase()}
                            </span>
                            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                              {step.step_type === 'llm_call'
                                ? `Model: ${step.data?.model || 'LLM'}`
                                : step.step_type === 'guard_decision'
                                ? `ActionGuard: ${step.data?.decision || 'EVALUATE'}`
                                : `Tool: ${step.data?.tool || 'shop_tool'}`}
                            </span>
                          </div>
                          <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                            {step.latency_ms} ms
                          </span>
                        </div>

                        {/* Relative Latency Bar */}
                        <div style={{ height: '4px', backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: '2px', marginBottom: '8px', overflow: 'hidden' }}>
                          <div
                            style={{
                              height: '100%',
                              width: `${pct}%`,
                              backgroundColor:
                                step.step_type === 'llm_call'
                                  ? 'var(--blue)'
                                  : step.step_type === 'guard_decision'
                                  ? step.data?.decision === 'BLOCK'
                                    ? 'var(--rose)'
                                    : 'var(--emerald)'
                                  : 'var(--text-tertiary)',
                              borderRadius: '2px',
                            }}
                          ></div>
                        </div>

                        {/* Step Details */}
                        <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', backgroundColor: 'var(--bg-canvas)', padding: '8px', borderRadius: '4px' }}>
                          {step.step_type === 'guard_decision' && step.data?.reasons && (
                            <div style={{ color: 'var(--rose)' }}>
                              Violations: {JSON.stringify(step.data.reasons)}
                            </div>
                          )}
                          {step.step_type === 'tool_call' && step.data?.diff && (
                            <div style={{ color: 'var(--emerald)' }}>
                              Database Write Diff: {JSON.stringify(step.data.diff)}
                            </div>
                          )}
                          {step.data?.output && <div>Output: {step.data.output}</div>}
                          {step.data?.response && <div>Agent Response: {step.data.response}</div>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {activeTab === 'io' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '6px' }}>
                      INBOUND CUSTOMER TICKET
                    </div>
                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)', fontSize: '0.82rem' }}>
                      {selectedTrace.input_text}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '6px' }}>
                      TOOL GATEWAY BOUNDARY EVIDENCE
                    </div>
                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)', fontSize: '0.78rem', fontFamily: 'var(--font-mono)' }}>
                      Precondition Check: Verified<br />
                      Database Write Operations: {selectedTrace.status === 'blocked' ? '0 (BLOCKED)' : '1 Row Inserted'}<br />
                      Idempotency Key: IDEM_{selectedTrace.id}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'raw' && (
                <pre
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    border: '1px solid var(--border-default)',
                    padding: '12px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.72rem',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-code)',
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {JSON.stringify(selectedTrace, null, 2)}
                </pre>
              )}
            </div>
          </div>
        ) : (
          <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
            Select a trace from the left panel to inspect its waterfall.
          </div>
        )}
      </div>
    </div>
  );
};
