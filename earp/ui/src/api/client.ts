/**
 * Proofline Enterprise API Client
 * Configured with Axios, JWT auth injection, and typed endpoints.
 */

import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT Bearer token from localStorage when present
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('proofline_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ---------------------------------------------------------------------------
// Typed API Calls
// ---------------------------------------------------------------------------

export const api = {
  // 1. Health & Status
  getHealth: async () => (await apiClient.get('/health')).data,

  // 2. Traces
  getTraceStats: async () => (await apiClient.get('/api/v1/traces/stats')).data,
  getTraces: async (params?: Record<string, any>) =>
    (await apiClient.get('/api/v1/traces', { params })).data,
  getTraceDetail: async (id: string) =>
    (await apiClient.get(`/api/v1/traces/${id}`)).data,

  // 3. Guard & Tool Gateway Approvals
  getApprovals: async (status?: string) =>
    (await apiClient.get('/api/v1/guard/approvals', { params: { status } })).data,
  approveAction: async (id: string, notes?: string) =>
    (await apiClient.post(`/api/v1/guard/approvals/${id}/approve`, {
      reviewer_id: 'dashboard_operator',
      notes: notes || 'Approved via Proofline Dashboard',
    })).data,
  rejectAction: async (id: string, notes?: string) =>
    (await apiClient.post(`/api/v1/guard/approvals/${id}/reject`, {
      reviewer_id: 'dashboard_operator',
      notes: notes || 'Rejected via Proofline Dashboard',
    })).data,

  // 4. Evaluations & Claim-vs-State Verifier
  runEvals: async (workflow?: string, max_cases?: number) =>
    (await apiClient.post('/api/v1/evals/run', { workflow, max_cases })).data,
  runRegression: async (workflow?: string) =>
    (await apiClient.post('/api/v1/evals/regression', { workflow })).data,
  verifyClaims: async (response_text: string, state_snapshot: Record<string, any>) =>
    (await apiClient.post('/api/v1/evals/verify-claims', {
      response_text,
      agent_response: response_text,
      state_snapshot,
    })).data,
  runPassK: async (k: number = 3, workflow?: string) =>
    (await apiClient.post('/api/v1/evals/passk', { k, workflow })).data,

  // 5. Watchdog, Anomaly & Reconciliation
  getWatchdogFindings: async () =>
    (await apiClient.get('/api/v1/watchdog/findings')).data,
  getAnomalyReport: async () =>
    (await apiClient.get('/api/v1/watchdog/anomaly/report')).data,
  runReconciliation: async (external_states?: any[]) =>
    (await apiClient.post('/api/v1/watchdog/reconcile', {
      external_states: external_states || [],
      persist_findings: true,
    })).data,
  getAlerts: async (limit: number = 50) =>
    (await apiClient.get('/api/v1/watchdog/alerts', { params: { limit } })).data,

  // 6. Security, Red Team & Conflicts
  runRedTeam: async () =>
    (await apiClient.post('/api/v1/redteam/run')).data,
  scanPolicyConflicts: async () =>
    (await apiClient.post('/api/v1/conflicts/scan')).data,
  inspectDLP: async (text: string) =>
    (await apiClient.post('/api/v1/security/inspect', { text })).data,

  // 7. Spend Guard
  getSpendSummary: async () =>
    (await apiClient.get('/api/v1/spend/summary')).data,

  // 8. Explicit Authentication & Session Controls
  login: async (username: string, password: string, role = 'operator', projectId = 'default') => {
    const res = await axios.post('/api/v1/auth/token', {
      username,
      password,
      role,
      project_id: projectId,
    });
    if (res.data?.access_token) {
      localStorage.setItem('proofline_token', res.data.access_token);
    }
    return res.data;
  },
  logout: () => {
    localStorage.removeItem('proofline_token');
  },
  isAuthenticated: () => {
    return Boolean(localStorage.getItem('proofline_token'));
  },
  devLoginAsOperator: async () => {
    // Explicit isolated operator authentication for local development/testing
    return await api.login('operator.engineer@proofline.ai', 'otp_verified', 'operator');
  },
};
