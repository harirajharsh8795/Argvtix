import { useState } from 'react';
import { LiveFeed } from '../components/LiveFeed';
import {
  Cpu,
  Play,
  Award,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sliders,
} from 'lucide-react';

interface ModelResult {
  model_id: string;
  accuracy_pct: number;
  p50_latency_ms: number;
  p90_latency_ms: number;
  total_cost_usd: number;
  passed: number;
  failed: number;
  errors: number;
}

interface BenchmarkRun {
  run_id: string;
  timestamp: string;
  total_models: number;
  total_cases: number;
  winner_accuracy: string;
  winner_cost: string;
  winner_latency: string;
  models: ModelResult[];
}

interface ModelOption {
  id: string;
  label: string;
  provider: 'Local' | 'Google' | 'Anthropic' | 'OpenAI';
  safe: boolean;
}

const AVAILABLE_MODELS: ModelOption[] = [
  { id: 'mock', label: 'Deterministic Mock Engine', provider: 'Local', safe: true },
  { id: 'gemini', label: 'Gemini 1.5 Pro', provider: 'Google', safe: false },
  { id: 'claude', label: 'Claude 3.5 Sonnet', provider: 'Anthropic', safe: false },
  { id: 'gpt4o', label: 'GPT-4o (Omni)', provider: 'OpenAI', safe: false },
  { id: 'gpt4o-mini', label: 'GPT-4o Mini', provider: 'OpenAI', safe: false },
];

const WORKFLOWS = ['', 'refund', 'cancel', 'balance', 'inventory', 'subscription', 'general'];

function AccuracyProgressBar({ pct }: { pct: number }) {
  const color = pct >= 80 ? 'var(--accent-success)' : pct >= 60 ? 'var(--accent-warning)' : 'var(--accent-danger)';
  return (
    <div style={{ width: '100%', background: 'var(--bg-canvas)', borderRadius: '4px', height: '6px', overflow: 'hidden', border: '1px solid var(--border-default)' }}>
      <div
        style={{
          width: `${Math.min(pct, 100)}%`,
          height: '100%',
          background: color,
          borderRadius: '4px',
          transition: 'width 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      />
    </div>
  );
}

function ModelRow({ r, run }: { r: ModelResult; run: BenchmarkRun }) {
  const isAccWinner = r.model_id === run.winner_accuracy;
  const isCostWinner = r.model_id === run.winner_cost;
  const isLatWinner = r.model_id === run.winner_latency;

  return (
    <div
      className="hover-card-elevate animate-fade-in-up"
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${isAccWinner ? 'rgba(99, 102, 241, 0.4)' : 'var(--border-default)'}`,
        borderRadius: 'var(--radius-md)',
        padding: '16px 18px',
        marginBottom: '12px',
        boxShadow: isAccWinner ? '0 0 16px rgba(99, 102, 241, 0.15)' : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-bright)', fontWeight: 700 }}>
            {r.model_id}
          </span>

          {isAccWinner && (
            <span
              className="badge"
              style={{
                background: 'rgba(16, 185, 129, 0.12)',
                color: 'var(--accent-success)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                fontSize: '0.65rem',
                fontWeight: 700,
              }}
            >
              TOP ACCURACY
            </span>
          )}

          {isCostWinner && (
            <span
              className="badge"
              style={{
                background: 'rgba(245, 158, 11, 0.12)',
                color: 'var(--accent-warning)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                fontSize: '0.65rem',
                fontWeight: 700,
              }}
            >
              LOWEST COST
            </span>
          )}

          {isLatWinner && (
            <span
              className="badge"
              style={{
                background: 'rgba(6, 182, 212, 0.12)',
                color: 'var(--accent-cyan)',
                border: '1px solid rgba(6, 182, 212, 0.3)',
                fontSize: '0.65rem',
                fontWeight: 700,
              }}
            >
              LOWEST LATENCY
            </span>
          )}
        </div>

        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-bright)', fontFamily: 'var(--font-mono)' }}>
          {r.accuracy_pct.toFixed(1)}%
        </div>
      </div>

      <AccuracyProgressBar pct={r.accuracy_pct} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '10px',
          marginTop: '12px',
          padding: '10px 12px',
          background: 'var(--bg-canvas)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-default)',
        }}
      >
        <div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Accuracy</div>
          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-bright)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            {r.accuracy_pct.toFixed(1)}%
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>P50 Latency</div>
          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-bright)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            {r.p50_latency_ms.toFixed(0)} ms
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>P90 Latency</div>
          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-bright)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            {r.p90_latency_ms.toFixed(0)} ms
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Total Cost</div>
          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-warning)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            ${r.total_cost_usd.toFixed(5)}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '14px', marginTop: '10px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
        <span style={{ color: 'var(--accent-success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <CheckCircle2 size={12} /> {r.passed} passed
        </span>
        <span style={{ color: 'var(--accent-danger)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <XCircle size={12} /> {r.failed} failed
        </span>
        {r.errors > 0 && (
          <span style={{ color: 'var(--accent-warning)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <AlertTriangle size={12} /> {r.errors} errors
          </span>
        )}
      </div>
    </div>
  );
}

export function BenchmarkPage() {
  const [selectedModels, setSelectedModels] = useState<string[]>(['mock']);
  const [workflow, setWorkflow] = useState('');
  const [maxCases, setMaxCases] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BenchmarkRun | null>(null);

  const toggleModel = (id: string) => {
    setSelectedModels((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const runBenchmark = async () => {
    if (selectedModels.length === 0) return;
    setLoading(true);
    setError(null);

    try {
      const tokenRes = await fetch('/api/v1/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'admin', password: 'admin', project_id: 'default', role: 'admin' }),
      });
      const { access_token } = await tokenRes.json();

      const res = await fetch('/api/v1/benchmarks/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${access_token}`,
        },
        body: JSON.stringify({
          models: selectedModels,
          workflow: workflow || null,
          max_cases: maxCases ? parseInt(maxCases) : null,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data: BenchmarkRun = await res.json();
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Model Comparison &amp; Benchmarks
            </span>
            <span style={{ color: '#334155' }}>•</span>
            <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Live WebSocket Telemetry Stream</span>
          </div>
          <h1 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.025em', margin: 0 }}>
            Multi-Model Reliability &amp; Cost Benchmarks
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginTop: '8px', maxWidth: '820px', lineHeight: 1.6 }}>
            Compare real-world invariant fidelity, P50/P90 latencies, and token costs across Gemini 1.5, Claude 3.5, and GPT-4o against 80 golden production scenarios.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '24px' }}>
        {/* Left: Configuration Panel */}
        <div className="card" style={{ padding: '24px', background: '#0d111a', height: 'fit-content' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
            <Sliders size={16} color="#10b981" />
            <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f8fafc', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Run Parameters
            </span>
          </div>

          {/* Model selection */}
          <div style={{ marginBottom: '18px' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Candidate Models
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {AVAILABLE_MODELS.map((m) => {
                const isSelected = selectedModels.includes(m.id);
                return (
                  <label
                    key={m.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                      background: isSelected ? 'var(--bg-elevated)' : 'var(--bg-canvas)',
                      border: `1px solid ${isSelected ? 'var(--border-strong)' : 'var(--border-default)'}`,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleModel(m.id)}
                      style={{ accentColor: 'var(--accent-primary)' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-bright)', fontWeight: 600 }}>{m.label}</div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{m.provider}</div>
                    </div>
                    {!m.safe && (
                      <span className="badge badge-neutral" style={{ fontSize: '0.62rem' }}>
                        API KEY
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          </div>

          {/* Workflow filter */}
          <div style={{ marginBottom: '14px' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Workflow Domain
            </div>
            <select
              value={workflow}
              onChange={(e) => setWorkflow(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-bright)',
                padding: '8px 10px',
                fontSize: '0.8rem',
                outline: 'none',
              }}
            >
              {WORKFLOWS.map((w) => (
                <option key={w} value={w}>
                  {w ? w.toUpperCase() : 'ALL WORKFLOWS'}
                </option>
              ))}
            </select>
          </div>

          {/* Max cases */}
          <div style={{ marginBottom: '18px' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Case Limit (Optional)
            </div>
            <input
              type="number"
              placeholder="All cases (80)"
              value={maxCases}
              onChange={(e) => setMaxCases(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-bright)',
                padding: '8px 10px',
                fontSize: '0.8rem',
                boxSizing: 'border-box',
                outline: 'none',
              }}
            />
          </div>

          <button
            id="btn-run-benchmark"
            onClick={runBenchmark}
            disabled={loading || selectedModels.length === 0}
            className="btn btn-primary"
            style={{ width: '100%' }}
          >
            <Play size={13} className={loading ? 'animate-spin' : ''} />
            <span>{loading ? 'Running Suite...' : 'Execute Benchmark'}</span>
          </button>

          {error && (
            <div
              style={{
                marginTop: '12px',
                padding: '8px 12px',
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                color: 'var(--accent-danger)',
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* Right: Results + Live Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Results Card */}
          <div className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Award size={18} color="var(--accent-primary)" />
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-bright)' }}>
                  Head-to-Head Comparison Results
                </span>
              </div>
            </div>

            {!result && !loading && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                <Cpu size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
                <div style={{ color: 'var(--text-bright)', fontWeight: 600, fontSize: '0.9rem' }}>No benchmark run active</div>
                <div style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                  Select models and click <strong>Execute Benchmark</strong> to compare accuracy and performance.
                </div>
              </div>
            )}

            {loading && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-secondary)' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-bright)' }}>
                  Executing parallel evaluations across candidate LLMs…
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Evaluating tool calling invariants, response grounding, and latency percentiles.
                </div>
              </div>
            )}

            {result && !loading && (
              <>
                {/* Run meta */}
                <div
                  style={{
                    display: 'flex',
                    gap: '16px',
                    flexWrap: 'wrap',
                    padding: '10px 14px',
                    background: 'var(--bg-canvas)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-sm)',
                    marginBottom: '16px',
                    fontSize: '0.75rem',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <span>Run ID: <strong style={{ color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}>{result.run_id}</strong></span>
                  <span>Cases: <strong style={{ color: 'var(--text-bright)' }}>{result.total_cases}</strong></span>
                  <span>Models: <strong style={{ color: 'var(--text-bright)' }}>{result.total_models}</strong></span>
                  <span>Timestamp: <strong style={{ color: 'var(--text-bright)' }}>{new Date(result.timestamp).toLocaleTimeString()}</strong></span>
                </div>

                {result.models.map((r) => (
                  <ModelRow key={r.model_id} r={r} run={result} />
                ))}
              </>
            )}
          </div>

          {/* Live Stream Terminal */}
          <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
            <LiveFeed height="380px" />
          </div>
        </div>
      </div>
    </div>
  );
}
