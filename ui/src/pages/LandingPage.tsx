import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Terminal,
  ArrowRight,
  ExternalLink,
  CheckCircle2,
  Copy,
  Check,
  Layers,
  Lock,
  Activity,
  FileText,
  Database,
  ChevronRight,
  ChevronDown,
  HelpCircle,
  Code2,
  X,
} from 'lucide-react';
import { ArgvtixLogo } from '../components/ArgvtixLogo';
import { AuthModal } from '../components/AuthModal';
import { usePageMetadata } from '../hooks/usePageMetadata';

interface ScenarioPreset {
  id: string;
  name: string;
  tool: string;
  payload: Record<string, unknown>;
  trigger: string;
  ruleCode: string;
  outcome: 'ALLOW' | 'ESCALATE' | 'BLOCK' | 'REDACT';
  outcomeColor: string;
  latencyMs: number;
  dbCommitted: boolean;
  explanation: string;
  rcaCategory: string;
  confidenceScore: string;
  downstreamImpact: string;
  evidence: string[];
  stepDetails: {
    precondition: string;
    astCheck: string;
    enforcement: string;
    dbCommit: string;
  };
}

const SCENARIOS: ScenarioPreset[] = [
  {
    id: 'scen-1',
    name: 'Normal Customer Refund (₹2,500)',
    tool: 'issue_refund',
    payload: { order_id: 'ord_1042', amount: 2500.0, customer_id: 'cust_881', reason: 'Size exchange requested' },
    trigger: 'Amount <= ₹10,000.00 and customer refund count == 0 this hour',
    ruleCode: 'POL-001: Max limit ₹10,000.00 | Speed <= 2 refunds / hour',
    outcome: 'ALLOW',
    outcomeColor: '#10b981',
    latencyMs: 1.2,
    dbCommitted: true,
    explanation: 'Passed all safety checks. The tool executed safely and the database was updated.',
    rcaCategory: 'SAFE_AND_PERMITTED',
    confidenceScore: '100% Deterministic Check',
    downstreamImpact: '₹2,500.00 debited from verified escrow. Order ord_1042 marked REFUNDED.',
    evidence: [
      'Customer has not requested any refund in the past 60 minutes',
      'Transaction amount is well within company policy limits',
      'Valid delivered order confirmed in local PostgreSQL',
    ],
    stepDetails: {
      precondition: 'Order ord_1042 confirmed DELIVERED. Customer refund speed: 0 in 60m.',
      astCheck: 'Rule check: ₹2,500 <= ₹10,000 is TRUE. Policy satisfied.',
      enforcement: 'Action approved automatically. Dispatched via Tool Gateway.',
      dbCommit: '1 row updated in orders table. Transaction saved with cryptographic audit hash.',
    },
  },
  {
    id: 'scen-2',
    name: 'High-Value Policy Cap Breach (₹18,500)',
    tool: 'issue_refund',
    payload: { order_id: 'ord_103', amount: 18500.0, customer_id: 'cust_003', reason: 'Customer escalated claim' },
    trigger: 'Policy Cap Exceeded: ₹18,500 is higher than automatic limit of ₹10,000',
    ruleCode: 'POL-001: Amount > ₹10,000 -> Hold for Human Review',
    outcome: 'ESCALATE',
    outcomeColor: '#f59e0b',
    latencyMs: 1.4,
    dbCommitted: false,
    explanation: 'Stopped before any money moved or database was touched. Sent to human supervisor for approval.',
    rcaCategory: 'FINANCIAL_LIMIT_EXCEEDED',
    confidenceScore: '100% Deterministic Check',
    downstreamImpact: 'Prevented unapproved ₹18,500.00 payment. Company budget protected with 0 loss.',
    evidence: [
      'Rule check: ₹18,500 is higher than the ₹10,000 limit',
      'Zero database rows changed while waiting for manager sign-off',
      'Proposal #appr_80419 created in the Human Review queue',
    ],
    stepDetails: {
      precondition: 'Order ord_103 verified. Customer lifetime value: ₹42,000.00.',
      astCheck: 'Rule check: ₹18,500 exceeds company maximum threshold of ₹10,000.',
      enforcement: 'Action held safely. Proposal sent to human review queue with digital signature.',
      dbCommit: '0 rows modified. Database unchanged until human manager clicks approve.',
    },
  },
  {
    id: 'scen-3',
    name: 'Cancel Order on Already Delivered Item',
    tool: 'cancel_order',
    payload: { order_id: 'ord_209', reason: 'Customer changed mind after delivery' },
    trigger: 'State Conflict: Order is already DELIVERED (Cannot cancel a delivered package)',
    ruleCode: 'POL-003: Can only cancel if order status is PENDING or PROCESSING',
    outcome: 'BLOCK',
    outcomeColor: '#f43f5e',
    latencyMs: 1.1,
    dbCommitted: false,
    explanation: 'Illegal database update blocked. Prevents ghost cancellations and inventory mismatch.',
    rcaCategory: 'INVALID_ORDER_STATE',
    confidenceScore: '100% Deterministic Check',
    downstreamImpact: 'Prevented warehouse inventory corruption and shipping carrier disputes.',
    evidence: [
      'Database record: ord_209 status is already marked DELIVERED',
      'Rule check: DELIVERED is not an allowed cancellation state',
      'Agent write was rejected before modifying the database',
    ],
    stepDetails: {
      precondition: 'Database check: ord_209 status is DELIVERED. Proof of delivery signed.',
      astCheck: 'Rule check: DELIVERED cannot transition back to CANCELLED.',
      enforcement: 'Illegal action blocked with error code ERR_STATE_INVARIANT_VIOLATION.',
      dbCommit: '0 rows mutated. Database and Shopify ERP remain perfectly synchronized.',
    },
  },
  {
    id: 'scen-4',
    name: 'Outbound Aadhaar & PAN Data Exfiltration',
    tool: 'send_sms_notification',
    payload: { customer_phone: '9876543210', text: 'Verification complete: Aadhaar 9876 5432 1098 and PAN ABCDE1234F verified.' },
    trigger: 'Privacy Guard: Aadhaar Verhoeff algorithm and PAN card regex matched',
    ruleCode: 'DLP-004: Automatically scrub Indian Aadhaar and PAN before sending',
    outcome: 'REDACT',
    outcomeColor: '#0ea5e9',
    latencyMs: 0.9,
    dbCommitted: true,
    explanation: 'Sensitive personal identifiers replaced with [AADHAAR_REDACTED] and [PAN_REDACTED].',
    rcaCategory: 'PERSONAL_DATA_LEAK_PREVENTED',
    confidenceScore: '99.9% Mathematical Scan',
    downstreamImpact: 'Keeps your company compliant with DPDP Act 2023. Zero raw PII leaked.',
    evidence: [
      '12-digit Aadhaar verified using Verhoeff mathematical checksum',
      'Income Tax PAN card pattern matched ABCDE1234F',
      'Data was masked in memory before leaving your servers',
    ],
    stepDetails: {
      precondition: 'Outgoing message scanned for 12-digit Aadhaar and 10-char PAN numbers.',
      astCheck: 'Verhoeff checksum valid. Income tax PAN regex pattern detected.',
      enforcement: 'Sensitive numbers masked in-memory. Clean message sent safely.',
      dbCommit: 'Sanitized audit log saved. Zero raw personal data stored on disk.',
    },
  },
];

interface CodeSnippetDefinition {
  title: string;
  filename: string;
  lines: Array<{ lineNum: string; tokens: Array<{ text: string; color: string; bold?: boolean }> }>;
}

const CODE_EXAMPLES: Record<'python' | 'mcp' | 'rest', CodeSnippetDefinition> = {
  python: {
    title: 'Python Safety Guard Setup',
    filename: 'guard_rules.py',
    lines: [
      { lineNum: '01', tokens: [{ text: '# 1. Set up automatic safety rules in Python', color: '#64748b' }] },
      { lineNum: '02', tokens: [{ text: 'from ', color: '#f43f5e', bold: true }, { text: 'argvtix.gateway ', color: '#e2e8f0' }, { text: 'import ', color: '#f43f5e', bold: true }, { text: 'ActionGuard, InvariantRule', color: '#38bdf8' }] },
      { lineNum: '03', tokens: [{ text: 'from ', color: '#f43f5e', bold: true }, { text: 'argvtix.evals ', color: '#e2e8f0' }, { text: 'import ', color: '#f43f5e', bold: true }, { text: 'ClaimVerifier', color: '#38bdf8' }] },
      { lineNum: '04', tokens: [] },
      { lineNum: '05', tokens: [{ text: 'guard = ', color: '#e2e8f0' }, { text: 'ActionGuard', color: '#38bdf8', bold: true }, { text: '(', color: '#cbd5e1' }] },
      { lineNum: '06', tokens: [{ text: '    rules=[', color: '#cbd5e1' }] },
      { lineNum: '07', tokens: [{ text: '        InvariantRule(', color: '#38bdf8' }] },
      { lineNum: '08', tokens: [{ text: '            tool=', color: '#94a3b8' }, { text: '"issue_refund"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '09', tokens: [{ text: '            condition=', color: '#94a3b8' }, { text: '"amount <= 10000.00 and customer_refunds_1h <= 2"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '10', tokens: [{ text: '            on_violation=', color: '#94a3b8' }, { text: '"ESCALATE_TO_HUMAN"', color: '#f59e0b', bold: true }] },
      { lineNum: '11', tokens: [{ text: '        ),', color: '#cbd5e1' }] },
      { lineNum: '12', tokens: [{ text: '        InvariantRule(', color: '#38bdf8' }] },
      { lineNum: '13', tokens: [{ text: '            tool=', color: '#94a3b8' }, { text: '"cancel_order"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '14', tokens: [{ text: '            condition=', color: '#94a3b8' }, { text: '"order.status in [\'PENDING\', \'PROCESSING\']"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '15', tokens: [{ text: '            on_violation=', color: '#94a3b8' }, { text: '"BLOCK"', color: '#f43f5e', bold: true }] },
      { lineNum: '16', tokens: [{ text: '        )', color: '#cbd5e1' }] },
      { lineNum: '17', tokens: [{ text: '    ]', color: '#cbd5e1' }] },
      { lineNum: '18', tokens: [{ text: ')', color: '#cbd5e1' }] },
      { lineNum: '19', tokens: [] },
      { lineNum: '20', tokens: [{ text: '# 2. Check the agent call BEFORE the database is updated', color: '#64748b' }] },
      { lineNum: '21', tokens: [{ text: 'decision = guard.', color: '#e2e8f0' }, { text: 'evaluate', color: '#38bdf8' }, { text: '(tool=', color: '#94a3b8' }, { text: '"issue_refund"', color: '#10b981' }, { text: ', payload={', color: '#cbd5e1' }, { text: '"amount"', color: '#10b981' }, { text: ': ', color: '#cbd5e1' }, { text: '18500.0', color: '#f59e0b' }, { text: '})', color: '#cbd5e1' }] },
      { lineNum: '22', tokens: [{ text: 'if ', color: '#f43f5e', bold: true }, { text: 'decision.is_escalated:', color: '#e2e8f0' }] },
      { lineNum: '23', tokens: [{ text: '    review_queue.submit_for_approval(decision.proposal_id)', color: '#94a3b8' }] },
    ],
  },
  mcp: {
    title: 'Anthropic MCP Proxy Configuration',
    filename: 'mcp_servers.json',
    lines: [
      { lineNum: '01', tokens: [{ text: '// Model Context Protocol (MCP) Safety Proxy', color: '#64748b' }] },
      { lineNum: '02', tokens: [{ text: '{', color: '#cbd5e1' }] },
      { lineNum: '03', tokens: [{ text: '  "mcpServers": {', color: '#e2e8f0' }] },
      { lineNum: '04', tokens: [{ text: '    "argvtix-gateway": {', color: '#38bdf8' }] },
      { lineNum: '05', tokens: [{ text: '      "command": ', color: '#94a3b8' }, { text: '"python"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '06', tokens: [{ text: '      "args": [', color: '#94a3b8' }, { text: '"-m"', color: '#10b981' }, { text: ', ', color: '#cbd5e1' }, { text: '"argvtix.gateway.mcp_proxy"', color: '#10b981' }, { text: '],', color: '#cbd5e1' }] },
      { lineNum: '07', tokens: [{ text: '      "env": {', color: '#94a3b8' }] },
      { lineNum: '08', tokens: [{ text: '        "SAFETY_MODE": ', color: '#94a3b8' }, { text: '"STRICT_ZERO_BYPASS"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '09', tokens: [{ text: '        "DATABASE_GUARD": ', color: '#94a3b8' }, { text: '"ACTIVE"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '10', tokens: [{ text: '        "LIVE_AUDIT_URL": ', color: '#94a3b8' }, { text: '"ws://127.0.0.1:8000/ws/events"', color: '#10b981' }] },
      { lineNum: '11', tokens: [{ text: '      }', color: '#cbd5e1' }] },
      { lineNum: '12', tokens: [{ text: '    }', color: '#cbd5e1' }] },
      { lineNum: '13', tokens: [{ text: '  }', color: '#cbd5e1' }] },
      { lineNum: '14', tokens: [{ text: '}', color: '#cbd5e1' }] },
    ],
  },
  rest: {
    title: 'REST API Request Example',
    filename: 'curl_check.sh',
    lines: [
      { lineNum: '01', tokens: [{ text: '# Check tool safety with a simple REST API call', color: '#64748b' }] },
      { lineNum: '02', tokens: [{ text: 'curl -X POST ', color: '#f43f5e', bold: true }, { text: '"http://127.0.0.1:8000/api/v1/guard/evaluate" \\', color: '#10b981' }] },
      { lineNum: '03', tokens: [{ text: '  -H ', color: '#38bdf8' }, { text: '"Authorization: Bearer ${API_KEY}" \\', color: '#10b981' }] },
      { lineNum: '04', tokens: [{ text: '  -H ', color: '#38bdf8' }, { text: '"Content-Type: application/json" \\', color: '#10b981' }] },
      { lineNum: '05', tokens: [{ text: '  -d \'{', color: '#cbd5e1' }] },
      { lineNum: '06', tokens: [{ text: '    "tool_name": ', color: '#94a3b8' }, { text: '"issue_refund"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '07', tokens: [{ text: '    "order_id": ', color: '#94a3b8' }, { text: '"ord_103"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '08', tokens: [{ text: '    "customer_id": ', color: '#94a3b8' }, { text: '"cust_003"', color: '#10b981' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '09', tokens: [{ text: '    "amount": ', color: '#94a3b8' }, { text: '18500.0', color: '#f59e0b' }, { text: ',', color: '#cbd5e1' }] },
      { lineNum: '10', tokens: [{ text: '    "reason": ', color: '#94a3b8' }, { text: '"Damaged parcel"', color: '#10b981' }, { text: '', color: '#cbd5e1' }] },
      { lineNum: '11', tokens: [{ text: '  }\'', color: '#cbd5e1' }] },
    ],
  },
};

export const LandingPage: React.FC = () => {
  usePageMetadata({
    title: 'Argvtix — Enterprise AI Reliability & Action Guard Platform',
    description:
      'Zero-bypass runtime policy guard, deterministic claim-state verification, and automated watchdog audits for autonomous enterprise AI agents.',
    canonicalUrl: 'https://argvtix.ai/',
  });

  const [activeCodeTab, setActiveCodeTab] = useState<'python' | 'mcp' | 'rest'>('python');
  const [activeScenario, setActiveScenario] = useState<ScenarioPreset>(SCENARIOS[1]);
  const [activeTourTab, setActiveTourTab] = useState<number>(0);
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedInstall, setCopiedInstall] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  const faqs = [
    {
      question: 'How does Action Guard differ from simple LLM prompt guardrails?',
      answer:
        'Traditional LLM guardrails rely on language model self-critique or probabilistic regex filters that can be bypassed via prompt injection or unexpected phrasing. Action Guard operates on the deterministic runtime execution layer as a pre-commit interceptor: regardless of what the LLM hallucinates or what prompt injection it encounters, the tool invocation payload is evaluated against deterministic invariant rules (e.g. amount <= ₹10,000, customer velocity limits, valid order states) before any database row or external API is reached. If a rule fails, the action is blocked or routed to a human supervisor with zero database mutations.',
    },
    {
      question: 'What is the latency overhead of inserting Argvtix into our agent execution path?',
      answer:
        'The pre-action Action Guard engine evaluates deterministic AST invariants in sub-2ms (average 1.2ms to 1.8ms on standard hardware). PII redaction using the Verhoeff mathematical algorithm and regex pattern matching completes in under 1ms. The system is designed to introduce zero perceptible lag to user-facing agent conversations.',
    },
    {
      question: 'Can Argvtix run entirely on-premises or within our private cloud VPC?',
      answer:
        'Yes. Argvtix is delivered as a containerized microservice suite (Docker Compose / Helm chart for Kubernetes) with zero outbound external dependencies. All invariant evaluations, trace ingestion, and watchdog scans execute locally against your private PostgreSQL instance. Customer telemetry and agent payloads never leave your network boundary.',
    },
    {
      question: 'How does Claim Verifier detect agent hallucinations in multi-lingual workflows?',
      answer:
        'Claim Verifier parses factual assertions from agent responses (in English, Hindi, and Hinglish) and validates them against the actual executed tool records and database mutations. If an agent states "Refund of ₹2,500 has been credited to your bank" but the tool invocation failed or was blocked by a policy cap, Claim Verifier immediately flags a "PHANTOM_ACTION" claim discrepancy and logs a high-severity alert.',
    },
    {
      question: 'How does Argvtix enforce compliance with the Indian Digital Personal Data Protection (DPDP) Act 2023 and GDPR?',
      answer:
        'ARGVTIX provides an automated in-memory PII/DLP redaction engine that verifies 12-digit Indian Aadhaar numbers via the Verhoeff checksum algorithm, identifies PAN cards, phone numbers, and payment details, and scrubs them before outbound transmission or audit logging. Customer data is never used for foundation model training or third-party sharing.',
    },
    {
      question: 'Does Argvtix support Anthropic Model Context Protocol (MCP) and custom agent frameworks?',
      answer:
        'Yes. Argvtix includes an MCP proxy adapter (argvtix.gateway.mcp_proxy) that wraps any standard MCP server or client (Claude Desktop, custom MCP agents), as well as native SDKs and REST APIs for LangChain, LangGraph, CrewAI, AutoGen, and custom Python toolkits.',
    },
  ];

  // Injects Schema.org FAQPage structured data into document head
  useEffect(() => {
    const schemaId = 'argvtix-faq-ld-json';
    let script = document.getElementById(schemaId) as HTMLScriptElement | null;
    if (!script) {
      script = document.createElement('script');
      script.id = schemaId;
      script.type = 'application/ld+json';
      document.head.appendChild(script);
    }
    script.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faqs.map((f) => ({
        '@type': 'Question',
        name: f.question,
        acceptedAnswer: {
          '@type': 'Answer',
          text: f.answer,
        },
      })),
    });

    return () => {
      script?.remove();
    };
  }, []);

  const handleCopyCode = () => {
    const codeStr = CODE_EXAMPLES[activeCodeTab].lines
      .map((l) => l.tokens.map((t) => t.text).join(''))
      .join('\n');
    navigator.clipboard.writeText(codeStr);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleCopyInstall = () => {
    navigator.clipboard.writeText('pip install argvtix-guard && docker compose up -d');
    setCopiedInstall(true);
    setTimeout(() => setCopiedInstall(false), 2000);
  };

  const tourTabs = [
    {
      title: 'Action Guard',
      subtitle: 'Stop Unauthorized Changes',
      tag: 'LAYER 1',
      description:
        'Prevents your AI from refunding too much money, spamming actions, or deleting active orders. Works on the live execution path in under 1.8 milliseconds without giving raw AI models direct access to your database.',
      points: [
        'Checks rules in under 1.8 milliseconds before any database row is touched',
        'Automatically routes high-value or risky actions to a human manager for approval',
        'Change safety rules easily anytime without rebuilding or redeploying code',
      ],
      badge: 'PRE-ACTION',
      metric: '100% Interception',
    },
    {
      title: 'Truth Verifier',
      subtitle: 'Catch AI Hallucinations',
      tag: 'LAYER 2',
      description:
        'Sometimes an AI agent tells a customer "Your refund has been issued", but the database write actually failed. Argvtix compares what the AI said in English, Hindi, or Hinglish against actual database changes to catch phantom actions.',
      points: [
        'Supports English, Hindi Devanagari, and everyday colloquial Hinglish',
        'Tests repeatedly across multiple runs (pass^k) to catch hidden model flakiness',
        'Includes an 80-case golden benchmark test suite for automated regression checks',
      ],
      badge: 'IN-LINE',
      metric: 'Strict pass^k',
    },
    {
      title: 'State Watchdog',
      subtitle: 'Audit & Sync Systems',
      tag: 'LAYER 3',
      description:
        'Runs silently in the background, watching for unusual spikes in agent activity and comparing your local database records with external platforms like Shopify ERP and Salesforce CRM to keep ledgers balanced.',
      points: [
        'Smart statistical anomaly detector flags sudden refund or cancellation surges',
        'Cross-checks Shopify and Salesforce ledgers to prevent ghost or duplicate records',
        'Catches negative balances and illegal status changes automatically',
      ],
      badge: 'POST-COMMIT',
      metric: 'Zero State Drift',
    },
    {
      title: 'Privacy & Security Guard',
      subtitle: 'Shield Data & Stop Attacks',
      tag: 'SECURITY',
      description:
        'Protects customer privacy by automatically detecting and masking Indian Aadhaar card numbers and PAN cards. Defends against prompt injection attacks, jailbreaks, and unauthorized privilege escalations.',
      points: [
        'Tested against 40 OWASP adversarial attack scenarios (prompt injection, jailbreak)',
        'Uses the official Verhoeff mathematical checksum algorithm for Indian Aadhaar validation',
        'Automatically scrubs sensitive customer details before sending outbound notifications',
      ],
      badge: 'SECURITY',
      metric: '38/40 Blocked',
    },
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#08090d', color: '#f8fafc', fontFamily: 'var(--font-sans)', overflowX: 'hidden' }}>
      {/* ──────────────────────────────────────────────────────────────────────────
          1. NAVIGATION BAR (Clean, perfectly balanced 3-column layout)
             Logo on Left, Nav Links Centered in Middle, Auth/Console on Right
         ────────────────────────────────────────────────────────────────────────── */}
      <nav
        style={{
          borderBottom: '1px solid #1a202c',
          background: 'rgba(8, 9, 13, 0.94)',
          backdropFilter: 'blur(16px)',
          padding: '0 32px',
          height: '68px',
          display: 'grid',
          gridTemplateColumns: 'auto 1fr auto',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        {/* Column 1 (Left): Brand Logo */}
        <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}>
          <ArgvtixLogo size={32} version="v1.2.0-prod" />
        </Link>

        {/* Column 2 (Center): Perfectly Centered Navigation Links */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '28px' }}>
          <a
            href="#playground"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            Live Simulator
          </a>
          <a
            href="#landscape"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            Comparison Matrix
          </a>
          <a
            href="#tour"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            How It Works
          </a>
          <a
            href="#comparison"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            Why Argvtix
          </a>
          <a
            href="#benchmarks"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            Verified Benchmarks
          </a>
          <a
            href="#faq"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            FAQ
          </a>
          <Link
            to="/contact"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            Request Demo
          </Link>
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
            style={{
              color: '#94a3b8',
              textDecoration: 'none',
              fontSize: '0.84rem',
              fontWeight: 500,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            <span>REST Docs</span>
            <ExternalLink size={12} color="#64748b" />
          </a>
        </div>

        {/* Column 3 (Right): Authentication & Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '14px' }}>
          <button
            id="nav-signin-btn"
            data-testid="nav-signin-btn"
            onClick={() => setIsAuthModalOpen(true)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#cbd5e1',
              fontSize: '0.84rem',
              fontWeight: 600,
              cursor: 'pointer',
              padding: '6px 12px',
              borderRadius: '4px',
              transition: 'color 0.15s ease, background 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#ffffff';
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#cbd5e1';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            Sign In / Register
          </button>

          <Link
            to="/overview"
            className="btn-action-primary"
            style={{ fontSize: '0.84rem', padding: '8px 16px' }}
          >
            <span>Launch Platform Console</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </nav>

      {/* ──────────────────────────────────────────────────────────────────────────
          2. HERO SECTION: Grand Centered Layout + Clear Words + Realistic IDE
         ────────────────────────────────────────────────────────────────────────── */}
      <section style={{ maxWidth: '1240px', margin: '0 auto', padding: '72px 24px 64px' }}>
        {/* Centered Eyebrow & Headline Block */}
        <div style={{ textAlign: 'center', maxWidth: '880px', margin: '0 auto 48px' }}>
          {/* Eyebrow Badge with Pulse Beacon */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.72rem',
                fontWeight: 700,
                color: '#10b981',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                padding: '4px 12px',
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <span className="pulse-beacon" />
              ACTIVE RUNTIME SAFETY GUARD
            </span>
            <span style={{ color: '#334155' }}>/</span>
            <span style={{ fontSize: '0.75rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
              BUILT FOR PRODUCTION AI AGENTS
            </span>
          </div>

          {/* Simple, Authoritative Main Headline */}
          <h1
            style={{
              fontSize: '3.4rem',
              fontWeight: 800,
              color: '#ffffff',
              letterSpacing: '-0.035em',
              lineHeight: 1.1,
              margin: '0 0 24px',
            }}
          >
            Keep Your AI Agents Safe, Compliant, and Under Control
          </h1>

          {/* Clear Subheadline */}
          <p
            style={{
              fontSize: '1.08rem',
              color: '#94a3b8',
              lineHeight: 1.65,
              margin: '0 auto 32px',
              maxWidth: '760px',
            }}
          >
            Argvtix stops autonomous AI agents from making unauthorized refunds, breaking database rules,
            or leaking customer data. Intercept risky tool calls before they happen, catch AI hallucinations, and audit your systems in real time.
          </p>

          {/* Centered Action Controls */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <Link
              to="/overview"
              className="btn-action-primary"
              style={{ padding: '12px 24px', fontSize: '0.92rem' }}
            >
              <span>Launch Platform Console</span>
              <ArrowRight size={15} />
            </Link>

            <a
              href="#playground"
              className="btn-action-secondary"
              style={{ padding: '12px 22px', fontSize: '0.92rem' }}
            >
              <Terminal size={15} color="#10b981" />
              <span>Interactive Safety Simulator</span>
            </a>

            <button
              onClick={handleCopyInstall}
              style={{
                padding: '12px 18px',
                fontSize: '0.8rem',
                fontWeight: 500,
                fontFamily: 'var(--font-mono)',
                borderRadius: '6px',
                background: '#0a0d13',
                border: '1px solid #1f2738',
                color: '#cbd5e1',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#38bdf8')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#1f2738')}
              title="Click to copy terminal command"
            >
              <span style={{ color: '#10b981' }}>$</span>
              <span>pip install argvtix-guard</span>
              {copiedInstall ? <Check size={13} color="#10b981" /> : <Copy size={13} color="#64748b" />}
            </button>
          </div>
        </div>

        {/* ──────────────────────────────────────────────────────────────────────────
            HERO SOFTWARE WINDOW (Ramotion / HackerRank Signature Centerpiece)
           ────────────────────────────────────────────────────────────────────────── */}
        <div
          style={{
            background: '#0d111a',
            border: '1px solid #222b3d',
            borderRadius: '8px',
            overflow: 'hidden',
            boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.05)',
          }}
        >
          {/* Window Chrome Titlebar */}
          <div
            style={{
              padding: '12px 18px',
              background: '#080a0f',
              borderBottom: '1px solid #1a202c',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            {/* Left: Window Controls & Path */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ff5f56' }} />
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ffbd2e' }} />
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#27c93f' }} />
              </div>
              <div style={{ height: 14, width: 1, background: '#1e2433' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Code2 size={13} color="#64748b" />
                <span style={{ color: '#64748b', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                  argvtix-runtime / gateway / {CODE_EXAMPLES[activeCodeTab].filename}
                </span>
              </div>
            </div>

            {/* Center: File Tabs */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <button
                onClick={() => setActiveCodeTab('python')}
                style={{
                  background: activeCodeTab === 'python' ? '#161c28' : 'transparent',
                  color: activeCodeTab === 'python' ? '#10b981' : '#64748b',
                  border: `1px solid ${activeCodeTab === 'python' ? '#283447' : 'transparent'}`,
                  borderRadius: '4px',
                  padding: '4px 10px',
                  fontSize: '0.72rem',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  transition: 'all 0.15s ease',
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: activeCodeTab === 'python' ? '#10b981' : '#475569' }} />
                <span>Python SDK</span>
              </button>
              <button
                onClick={() => setActiveCodeTab('mcp')}
                style={{
                  background: activeCodeTab === 'mcp' ? '#161c28' : 'transparent',
                  color: activeCodeTab === 'mcp' ? '#38bdf8' : '#64748b',
                  border: `1px solid ${activeCodeTab === 'mcp' ? '#283447' : 'transparent'}`,
                  borderRadius: '4px',
                  padding: '4px 10px',
                  fontSize: '0.72rem',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  transition: 'all 0.15s ease',
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: activeCodeTab === 'mcp' ? '#38bdf8' : '#475569' }} />
                <span>MCP Proxy Config</span>
              </button>
              <button
                onClick={() => setActiveCodeTab('rest')}
                style={{
                  background: activeCodeTab === 'rest' ? '#161c28' : 'transparent',
                  color: activeCodeTab === 'rest' ? '#f59e0b' : '#64748b',
                  border: `1px solid ${activeCodeTab === 'rest' ? '#283447' : 'transparent'}`,
                  borderRadius: '4px',
                  padding: '4px 10px',
                  fontSize: '0.72rem',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  transition: 'all 0.15s ease',
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: activeCodeTab === 'rest' ? '#f59e0b' : '#475569' }} />
                <span>REST API</span>
              </button>
            </div>

            {/* Right: Live Status Pill & Copy Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  fontSize: '0.68rem',
                  fontFamily: 'var(--font-mono)',
                  color: '#10b981',
                  background: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span className="pulse-beacon" style={{ width: 5, height: 5 }} />
                <span>PORT 8000 LIVE</span>
              </div>

              <button
                onClick={handleCopyCode}
                style={{
                  background: '#121620',
                  border: '1px solid #222938',
                  borderRadius: '4px',
                  color: '#cbd5e1',
                  padding: '3px 8px',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
                title="Copy snippet"
              >
                {copiedCode ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                <span>{copiedCode ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>

          {/* Window Body: Syntax-Highlighted Code (Left) & Assessment Scorecard (Right) */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 0.85fr', minHeight: '440px' }}>
            {/* Left: Syntax Highlighted IDE Editor */}
            <div
              style={{
                background: '#07090e',
                borderRight: '1px solid #1a202c',
                padding: '20px 16px',
                overflowX: 'auto',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.78rem',
                lineHeight: 1.7,
              }}
            >
              {CODE_EXAMPLES[activeCodeTab].lines.map((line, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    background: idx === 9 || idx === 10 ? 'rgba(245, 158, 11, 0.07)' : 'transparent',
                    borderRadius: '2px',
                    padding: '0 4px',
                  }}
                >
                  <span
                    style={{
                      width: '32px',
                      color: '#475569',
                      userSelect: 'none',
                      textAlign: 'right',
                      paddingRight: '14px',
                      flexShrink: 0,
                      fontSize: '0.72rem',
                    }}
                  >
                    {line.lineNum}
                  </span>
                  <div style={{ flex: 1, whiteSpace: 'pre' }}>
                    {line.tokens.length === 0 ? (
                      <span>&nbsp;</span>
                    ) : (
                      line.tokens.map((tok, tidx) => (
                        <span key={tidx} style={{ color: tok.color, fontWeight: tok.bold ? 700 : 400 }}>
                          {tok.text}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Right: Authentic Invariant Evaluation Scorecard */}
            <div
              style={{
                background: '#0a0d14',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              {/* Scorecard Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #1a202c', paddingBottom: '12px' }}>
                <div>
                  <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
                    INVARIANT EVALUATION SCORECARD
                  </div>
                  <div style={{ fontSize: '1rem', fontWeight: 800, color: '#f8fafc', marginTop: '2px' }}>
                    Tool Intercept : issue_refund
                  </div>
                </div>

                <div
                  style={{
                    fontSize: '0.72rem',
                    fontFamily: 'var(--font-mono)',
                    color: '#10b981',
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontWeight: 700,
                  }}
                >
                  4/4 RULES CHECKED
                </div>
              </div>

              {/* Invariant Rules Checklist */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {/* Rule 1 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px 12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={13} color="#f59e0b" />
                      <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#f8fafc' }}>
                        POL-001 Financial Policy Cap
                      </span>
                    </div>
                    <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#f59e0b', fontWeight: 700 }}>
                      HOLD FOR HUMAN
                    </span>
                  </div>
                  <div style={{ fontSize: '0.71rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                    amount ₹18,500 &gt; automatic limit ₹10,000 (0.82ms)
                  </div>
                </div>

                {/* Rule 2 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px 12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={13} color="#10b981" />
                      <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#f8fafc' }}>
                        POL-002 Velocity Rate Limiter
                      </span>
                    </div>
                    <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#10b981', fontWeight: 700 }}>
                      PASS
                    </span>
                  </div>
                  <div style={{ fontSize: '0.71rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                    customer.refunds_1h == 0 (allowed &lt;= 2) (0.19ms)
                  </div>
                </div>

                {/* Rule 3 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px 12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={13} color="#10b981" />
                      <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#f8fafc' }}>
                        POL-003 State Precondition Guard
                      </span>
                    </div>
                    <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#10b981', fontWeight: 700 }}>
                      PASS
                    </span>
                  </div>
                  <div style={{ fontSize: '0.71rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                    ord_103 status is PROCESSING (valid state) (0.24ms)
                  </div>
                </div>

                {/* Rule 4 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px 12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={13} color="#10b981" />
                      <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#f8fafc' }}>
                        Layer 1 DLP Data Sanitizer
                      </span>
                    </div>
                    <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#10b981', fontWeight: 700 }}>
                      CLEAN
                    </span>
                  </div>
                  <div style={{ fontSize: '0.71rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                    Aadhaar Verhoeff &amp; PAN scan: 0 exposed numbers (0.31ms)
                  </div>
                </div>
              </div>

              {/* Confidence & Hot-Path Telemetry Strip */}
              <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid #1a202c' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
                  <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '8px 10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b', textTransform: 'uppercase' }}>OVERHEAD LATENCY</div>
                    <div style={{ fontSize: '0.98rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>
                      1.32 ms
                    </div>
                  </div>
                  <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '8px 10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b', textTransform: 'uppercase' }}>DATABASE WRITES</div>
                    <div style={{ fontSize: '0.98rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                      0 MUTATIONS
                    </div>
                  </div>
                </div>

                <div style={{ fontSize: '0.7rem', color: '#94a3b8', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>Result: Proposal #appr_80419 Pending</span>
                  <span style={{ color: '#f59e0b', fontWeight: 600 }}>Human Review Active</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ──────────────────────────────────────────────────────────────────────────
            SUPPORTED FRAMEWORKS STRIP
           ────────────────────────────────────────────────────────────────────────── */}
        <div
          style={{
            marginTop: '36px',
            padding: '18px 24px',
            background: '#0a0d13',
            border: '1px solid #191f2c',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            WORKS WITH ALL MAJOR AGENT FRAMEWORKS:
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
            {['LangChain', 'CrewAI', 'LlamaIndex', 'Anthropic MCP', 'OpenAI Tool Calling', 'AutoGPT'].map((fw) => (
              <div key={fw} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#38bdf8' }} />
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#cbd5e1' }}>{fw}</span>
              </div>
            ))}
          </div>

          <div style={{ fontSize: '0.72rem', color: '#10b981', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
            ZERO DIRECT SQL ACCESS GIVEN TO MODELS
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          3. MARKET POSITIONING MATRIX (ContextQA, Testers.ai, Testrig, DeviQA vs Argvtix)
         ────────────────────────────────────────────────────────────────────────── */}
      <section id="landscape" style={{ borderTop: '1px solid #1a1e29', borderBottom: '1px solid #1a1e29', background: '#0a0d14', padding: '72px 24px' }}>
        <div style={{ maxWidth: '1240px', margin: '0 auto' }}>
          {/* Header */}
          <div style={{ textAlign: 'center', maxWidth: '820px', margin: '0 auto 36px' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
              HOW ARGVTIX COMPARES
            </div>
            <h2 style={{ fontSize: '2.2rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.025em', margin: '0 0 12px' }}>
              Understanding the AI Testing &amp; Reliability Landscape
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '0.94rem', margin: 0, lineHeight: 1.6 }}>
              Existing testing tools focus on clicking web pages or checking code inside an IDE.
              Argvtix provides the missing runtime safety layer that protects your production databases, APIs, and money while AI agents run live.
            </p>
          </div>

          {/* 5-Column Landscape Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '28px' }}>
            {/* Card 1: ContextQA */}
            <div className="hover-card-elevate" style={{ background: '#0d111a', border: '1px solid #1c2333', borderRadius: '6px', padding: '18px 16px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                WEB &amp; APP TESTING
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#f8fafc', marginBottom: '6px' }}>
                ContextQA
              </div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8', lineHeight: 1.45, marginBottom: '14px', flex: 1 }}>
                Generates and fixes UI tests for websites, mobile apps, and Salesforce.
              </div>
              <div style={{ borderTop: '1px solid #19202e', paddingTop: '10px', fontSize: '0.7rem', color: '#64748b' }}>
                <div><strong>When:</strong> Before launching software</div>
                <div style={{ marginTop: '3px' }}><strong>Protection:</strong> Web buttons &amp; UI forms</div>
              </div>
            </div>

            {/* Card 2: Testers.ai (CARBON) */}
            <div className="hover-card-elevate" style={{ background: '#0d111a', border: '1px solid #1c2333', borderRadius: '6px', padding: '18px 16px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                IN-IDE CODE TESTS
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#f8fafc', marginBottom: '6px' }}>
                Testers.ai (CARBON)
              </div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8', lineHeight: 1.45, marginBottom: '14px', flex: 1 }}>
                Runs code tests inside Cursor and Claude Code while developers write software.
              </div>
              <div style={{ borderTop: '1px solid #19202e', paddingTop: '10px', fontSize: '0.7rem', color: '#64748b' }}>
                <div><strong>When:</strong> During coding in IDE</div>
                <div style={{ marginTop: '3px' }}><strong>Protection:</strong> Code quality &amp; unit tests</div>
              </div>
            </div>

            {/* Card 3: Testrig Tech */}
            <div className="hover-card-elevate" style={{ background: '#0d111a', border: '1px solid #1c2333', borderRadius: '6px', padding: '18px 16px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                QE SERVICES
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#f8fafc', marginBottom: '6px' }}>
                Testrig Tech
              </div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8', lineHeight: 1.45, marginBottom: '14px', flex: 1 }}>
                Quality engineering consulting firm testing AI models and enterprise platforms.
              </div>
              <div style={{ borderTop: '1px solid #19202e', paddingTop: '10px', fontSize: '0.7rem', color: '#64748b' }}>
                <div><strong>When:</strong> Sprint QA audits</div>
                <div style={{ marginTop: '3px' }}><strong>Protection:</strong> Staging test reports</div>
              </div>
            </div>

            {/* Card 4: DeviQA */}
            <div className="hover-card-elevate" style={{ background: '#0d111a', border: '1px solid #1c2333', borderRadius: '6px', padding: '18px 16px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                FULL QA AGENCY
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#f8fafc', marginBottom: '6px' }}>
                DeviQA
              </div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8', lineHeight: 1.45, marginBottom: '14px', flex: 1 }}>
                Full-service software testing firm with AI copilots and test automation scripts.
              </div>
              <div style={{ borderTop: '1px solid #19202e', paddingTop: '10px', fontSize: '0.7rem', color: '#64748b' }}>
                <div><strong>When:</strong> Pre-release regression</div>
                <div style={{ marginTop: '3px' }}><strong>Protection:</strong> Manual &amp; script reports</div>
              </div>
            </div>

            {/* Card 5: Argvtix (Hero Highlight) */}
            <div className="hover-card-elevate" style={{ background: '#0f1624', border: '2px solid #10b981', borderRadius: '6px', padding: '18px 16px', display: 'flex', flexDirection: 'column', boxShadow: '0 8px 24px rgba(16, 185, 129, 0.15)' }}>
              <div style={{ fontSize: '0.66rem', color: '#10b981', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px' }}>
                RUNTIME PROTECTION
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#ffffff', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>Argvtix</span>
                <span style={{ fontSize: '0.6rem', background: '#10b981', color: '#000', padding: '1px 5px', borderRadius: '3px', fontWeight: 800 }}>LIVE</span>
              </div>
              <div style={{ fontSize: '0.74rem', color: '#cbd5e1', lineHeight: 1.45, marginBottom: '14px', flex: 1 }}>
                Real-time safety guard that intercepts agent tool calls and prevents unauthorized database writes.
              </div>
              <div style={{ borderTop: '1px solid #1e3a30', paddingTop: '10px', fontSize: '0.7rem', color: '#a7f3d0' }}>
                <div><strong>When:</strong> Live in production</div>
                <div style={{ marginTop: '3px' }}><strong>Protection:</strong> Blocks bad SQL &amp; payments</div>
              </div>
            </div>
          </div>

          {/* Matrix Table */}
          <div style={{ background: '#0d111a', border: '1px solid #1e2637', borderRadius: '6px', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#07090e', borderBottom: '1px solid #1a2233' }}>
                  <th style={{ padding: '12px 16px', color: '#64748b', fontWeight: 700 }}>CAPABILITY</th>
                  <th style={{ padding: '12px 16px', color: '#94a3b8' }}>ContextQA</th>
                  <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Testers.ai (CARBON)</th>
                  <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Testrig / DeviQA</th>
                  <th style={{ padding: '12px 16px', color: '#10b981', fontWeight: 700 }}>Argvtix</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid #141b27' }}>
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: '#f8fafc' }}>Execution Moment</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Before release (CI/CD)</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>While writing code in IDE</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Staging &amp; sprint audits</td>
                  <td style={{ padding: '12px 16px', color: '#10b981', fontWeight: 700 }}>Live runtime (&lt; 1.8ms before DB commit)</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #141b27' }}>
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: '#f8fafc' }}>Can Block Bad Database Writes?</td>
                  <td style={{ padding: '12px 16px', color: '#64748b' }}>No (Tests UI buttons)</td>
                  <td style={{ padding: '12px 16px', color: '#64748b' }}>No (Tests code functions)</td>
                  <td style={{ padding: '12px 16px', color: '#64748b' }}>No (Reports after bugs happen)</td>
                  <td style={{ padding: '12px 16px', color: '#10b981', fontWeight: 700 }}>Yes (Zero writes allowed on violation)</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #141b27' }}>
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: '#f8fafc' }}>Database Ground-Truth Verification</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>DOM element check</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Function assertion match</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Manual or script checks</td>
                  <td style={{ padding: '12px 16px', color: '#10b981', fontWeight: 700 }}>Mathematical SQL diff vs propositional claims</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #141b27' }}>
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: '#f8fafc' }}>Protects Against AI Flakiness</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Self-heals broken locators</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Evidence confidence scores</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Clusters flaky tests</td>
                  <td style={{ padding: '12px 16px', color: '#10b981', fontWeight: 700 }}>Strict pass^k multi-trial variance check</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: '#f8fafc' }}>Deployment Model</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Cloud SaaS</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>IDE Plugin</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8' }}>Agency Team &amp; Copilots</td>
                  <td style={{ padding: '12px 16px', color: '#10b981', fontWeight: 700 }}>100% Self-Hosted Docker &amp; Kubernetes</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          4. INTERACTIVE INVARIANT SIMULATOR (Playground)
         ────────────────────────────────────────────────────────────────────────── */}
      <section id="playground" style={{ borderTop: '1px solid #1a1e29', borderBottom: '1px solid #1a1e29', background: '#090b10', padding: '72px 24px' }}>
        <div style={{ maxWidth: '1240px', margin: '0 auto' }}>
          {/* Header */}
          <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 36px' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
              INTERACTIVE SIMULATOR
            </div>
            <h2 style={{ fontSize: '2.2rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.025em', margin: '0 0 12px' }}>
              See How Argvtix Protects Your Systems Live
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '0.94rem', margin: 0, lineHeight: 1.6 }}>
              Select any of the 4 real-world scenarios below to watch how Argvtix inspects, permits, holds, or blocks agent tool calls in real time.
            </p>
          </div>

          {/* Symmetrical 4-Scenario Selector Strip */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '24px' }}>
            {SCENARIOS.map((scen) => {
              const isSelected = activeScenario.id === scen.id;
              return (
                <button
                  key={scen.id}
                  onClick={() => setActiveScenario(scen)}
                  className="hover-card-elevate"
                  style={{
                    background: isSelected ? '#131824' : '#0d1017',
                    border: `1px solid ${isSelected ? '#33425e' : '#1a202c'}`,
                    borderTop: `3px solid ${isSelected ? scen.outcomeColor : 'transparent'}`,
                    borderRadius: '6px',
                    padding: '14px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    boxShadow: isSelected ? '0 6px 16px rgba(0,0,0,0.35)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
                      {scen.tool}
                    </span>
                    <span
                      style={{
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        color: scen.outcomeColor,
                        background: `${scen.outcomeColor}18`,
                        border: `1px solid ${scen.outcomeColor}30`,
                        padding: '1px 6px',
                        borderRadius: '3px',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {scen.outcome}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.84rem', fontWeight: 700, color: isSelected ? '#ffffff' : '#cbd5e1', lineHeight: 1.3 }}>
                    {scen.name}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Symmetrical Dual-Panel Simulator Workbench */}
          <div
            style={{
              background: '#0d111a',
              border: '1px solid #222b3d',
              borderRadius: '8px',
              overflow: 'hidden',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
            }}
          >
            {/* Left: Inbound Tool Invocation (MCP Frame) */}
            <div style={{ background: '#07090e', borderRight: '1px solid #1a202c', padding: '24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #161b26', paddingBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Terminal size={14} color="#38bdf8" />
                  <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
                    INCOMING AI TOOL CALL (MCP)
                  </span>
                </div>
                <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
                  session_id: ses_88419
                </span>
              </div>

              {/* Caller Metadata Strip */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div style={{ background: '#0b0e14', border: '1px solid #1a202c', borderRadius: '4px', padding: '8px 10px' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b' }}>CALLING MODEL</div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#cbd5e1', fontFamily: 'var(--font-mono)' }}>
                    claude-3-7-sonnet
                  </div>
                </div>
                <div style={{ background: '#0b0e14', border: '1px solid #1a202c', borderRadius: '4px', padding: '8px 10px' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b' }}>TARGET TOOL</div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                    {activeScenario.tool}()
                  </div>
                </div>
              </div>

              {/* Formatted JSON Payload */}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '6px', fontWeight: 600 }}>
                  RAW TOOL ARGUMENTS
                </div>
                <pre
                  style={{
                    margin: 0,
                    background: '#090b10',
                    border: '1px solid #1a202c',
                    borderRadius: '4px',
                    padding: '14px',
                    fontSize: '0.8rem',
                    color: '#e2e8f0',
                    fontFamily: 'var(--font-mono)',
                    lineHeight: 1.6,
                    overflowX: 'auto',
                  }}
                >
                  {JSON.stringify(activeScenario.payload, null, 2)}
                </pre>
              </div>

              {/* Policy Rule Check */}
              <div style={{ background: '#0c1017', border: '1px solid #1a2232', borderRadius: '4px', padding: '10px 12px' }}>
                <div style={{ fontSize: '0.66rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
                  ACTIVE SAFETY RULE
                </div>
                <div style={{ fontSize: '0.76rem', color: '#e2e8f0', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                  {activeScenario.ruleCode}
                </div>
              </div>
            </div>

            {/* Right: Decision Engine */}
            <div style={{ background: '#0a0d14', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Decision Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1a202c', paddingBottom: '12px' }}>
                <div>
                  <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
                    SAFETY DECISION
                  </div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#f8fafc', marginTop: '2px' }}>
                    {activeScenario.name}
                  </div>
                </div>

                <span
                  style={{
                    fontSize: '0.82rem',
                    fontWeight: 800,
                    color: activeScenario.outcomeColor,
                    background: `${activeScenario.outcomeColor}18`,
                    border: `1px solid ${activeScenario.outcomeColor}40`,
                    padding: '5px 12px',
                    borderRadius: '4px',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  ACTION: {activeScenario.outcome}
                </span>
              </div>

              {/* RCA & Confidence Bar */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div style={{ background: '#0d121c', border: '1px solid #1e283b', borderRadius: '4px', padding: '8px 10px' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b', textTransform: 'uppercase' }}>CATEGORY</div>
                  <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#f8fafc', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                    {activeScenario.rcaCategory}
                  </div>
                </div>
                <div style={{ background: '#0d121c', border: '1px solid #1e283b', borderRadius: '4px', padding: '8px 10px' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b', textTransform: 'uppercase' }}>ACCURACY GUARANTEE</div>
                  <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#10b981', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                    {activeScenario.confidenceScore}
                  </div>
                </div>
              </div>

              {/* Step-by-Step Pipeline Execution */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {/* Step 1 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '9px 12px' }}>
                  <div style={{ fontSize: '0.66rem', color: '#38bdf8', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: '2px' }}>
                    STEP 1 : CHECK EXISTING STATUS
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#cbd5e1' }}>
                    {activeScenario.stepDetails.precondition}
                  </div>
                </div>

                {/* Step 2 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '9px 12px' }}>
                  <div style={{ fontSize: '0.66rem', color: '#f59e0b', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: '2px' }}>
                    STEP 2 : EVALUATE POLICY RULE
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#cbd5e1' }}>
                    {activeScenario.stepDetails.astCheck}
                  </div>
                </div>

                {/* Step 3 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '9px 12px' }}>
                  <div style={{ fontSize: '0.66rem', color: activeScenario.outcomeColor, fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: '2px' }}>
                    STEP 3 : TAKE ENFORCEMENT ACTION
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#cbd5e1' }}>
                    {activeScenario.stepDetails.enforcement}
                  </div>
                </div>

                {/* Step 4 */}
                <div style={{ background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px', padding: '9px 12px' }}>
                  <div style={{ fontSize: '0.66rem', color: '#10b981', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: '2px' }}>
                    STEP 4 : DOWNSTREAM VALUE PROTECTED
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#a7f3d0' }}>
                    {activeScenario.downstreamImpact}
                  </div>
                </div>
              </div>

              {/* Status Bar */}
              <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid #1a202c', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                <div style={{ padding: '8px 10px', background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b' }}>RESPONSE TIME</div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
                    {activeScenario.latencyMs} ms
                  </div>
                </div>
                <div style={{ padding: '8px 10px', background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b' }}>DATABASE WRITE</div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 800, color: activeScenario.dbCommitted ? '#10b981' : '#f43f5e', fontFamily: 'var(--font-mono)' }}>
                    {activeScenario.dbCommitted ? 'COMMITTED' : '0 WRITE'}
                  </div>
                </div>
                <div style={{ padding: '8px 10px', background: '#0e121a', border: '1px solid #1c2331', borderRadius: '4px' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b' }}>SECURITY PROTOCOL</div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                    ZERO-BYPASS
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          5. FOUR DEFENSIVE LAYERS (Architecture Tour)
         ────────────────────────────────────────────────────────────────────────── */}
      <section id="tour" style={{ maxWidth: '1240px', margin: '0 auto', padding: '72px 24px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 36px' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
            HOW IT WORKS
          </div>
          <h2 style={{ fontSize: '2.2rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.025em', margin: '0 0 12px' }}>
            Four Coordinated Defenses Against AI Failures
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.94rem', margin: 0, lineHeight: 1.6 }}>
            Argvtix protects your application before, during, and after an AI agent takes an action.
          </p>
        </div>

        {/* 4 Tabs */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '8px',
            marginBottom: '24px',
            background: '#0d1017',
            border: '1px solid #1a202c',
            borderRadius: '6px',
            padding: '4px',
          }}
        >
          {tourTabs.map((tab, idx) => (
            <button
              key={idx}
              onClick={() => setActiveTourTab(idx)}
              className="hover-card-elevate"
              style={{
                background: activeTourTab === idx ? '#161c28' : 'transparent',
                border: `1px solid ${activeTourTab === idx ? '#2a3547' : 'transparent'}`,
                borderRadius: '4px',
                padding: '12px 14px',
                textAlign: 'left',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontSize: '0.68rem', fontWeight: 700, color: activeTourTab === idx ? '#10b981' : '#64748b', fontFamily: 'var(--font-mono)' }}>
                {tab.tag}
              </div>
              <div style={{ fontSize: '0.86rem', fontWeight: 700, color: activeTourTab === idx ? '#f8fafc' : '#94a3b8', marginTop: '2px' }}>
                {tab.title}
              </div>
            </button>
          ))}
        </div>

        {/* Tab Content: Balanced 50/50 Split */}
        <div
          style={{
            background: '#0d111a',
            border: '1px solid #212635',
            borderRadius: '8px',
            padding: '36px',
            display: 'grid',
            gridTemplateColumns: '1.1fr 0.9fr',
            gap: '36px',
            alignItems: 'center',
          }}
        >
          {/* Left: Description & Points */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <span
                style={{
                  fontSize: '0.7rem',
                  fontFamily: 'var(--font-mono)',
                  color: '#10b981',
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontWeight: 700,
                }}
              >
                {tourTabs[activeTourTab].badge}
              </span>
              <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
                {tourTabs[activeTourTab].subtitle}
              </span>
            </div>

            <h3 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f8fafc', margin: '0 0 14px' }}>
              {tourTabs[activeTourTab].title}
            </h3>

            <p style={{ fontSize: '0.92rem', color: '#94a3b8', lineHeight: 1.65, margin: '0 0 24px' }}>
              {tourTabs[activeTourTab].description}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {tourTabs[activeTourTab].points.map((pt, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  <CheckCircle2 size={16} color="#10b981" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span style={{ fontSize: '0.86rem', color: '#cbd5e1', lineHeight: 1.5 }}>{pt}</span>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '28px' }}>
              <Link
                to="/overview"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.84rem',
                  fontWeight: 600,
                  color: '#10b981',
                  textDecoration: 'none',
                }}
              >
                <span>Inspect this layer in the Platform Console</span>
                <ChevronRight size={14} />
              </Link>
            </div>
          </div>

          {/* Right: Concrete Mockup Visualizer */}
          <div
            style={{
              background: '#07090e',
              border: '1px solid #1a202c',
              borderRadius: '6px',
              padding: '22px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}
          >
            {activeTourTab === 0 && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                    LAYER 1 : HOT-PATH INTERCEPTOR
                  </span>
                  <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#10b981' }}>
                    100% Interception
                  </span>
                </div>
                <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '0.76rem' }}>
                  <div style={{ color: '#38bdf8' }}>[INTERCEPT] POST /api/v1/tools/execute</div>
                  <div style={{ color: '#94a3b8', margin: '4px 0' }}>entity="ord_103" tool="issue_refund"</div>
                  <div style={{ color: '#f59e0b' }}>eval(amount &lt;= 10000.00) -&gt; FALSE (18500.00)</div>
                  <div style={{ color: '#10b981', marginTop: '4px' }}>ROUTED -&gt; Human supervisor review queue</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b' }}>P95 LATENCY</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>&lt; 1.8 ms</div>
                  </div>
                  <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b' }}>SQL WRITES</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>0 COMMITTED</div>
                  </div>
                </div>
              </>
            )}

            {activeTourTab === 1 && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                    LAYER 2 : CLAIM-VS-STATE GROUNDING
                  </span>
                  <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>
                    Strict pass^k
                  </span>
                </div>
                <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '12px', fontSize: '0.76rem' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '2px' }}>AI TEXT CLAIM TO CUSTOMER</div>
                  <div style={{ color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>"मैंने आपका ₹2,500 का रिफंड सफलतापूर्वक प्रोसेस कर दिया है।"</div>
                </div>
                <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '12px', fontSize: '0.76rem' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '2px' }}>ACTUAL DATABASE GROUND TRUTH</div>
                  <div style={{ color: '#10b981', fontFamily: 'var(--font-mono)' }}>orders.refund_amount == 2500.00 | rows_mutated == 1 [MATCH CONFIRMED]</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.74rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                  <span>Multilingual: EN / HI / Hinglish</span>
                  <span style={{ color: '#10b981' }}>0 Hallucination Detected</span>
                </div>
              </>
            )}

            {activeTourTab === 2 && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                    LAYER 3 : STATISTICAL ANOMALY &amp; ERP AUDIT
                  </span>
                  <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#f59e0b' }}>
                    Zero State Drift
                  </span>
                </div>
                <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '0.76rem' }}>
                  <div style={{ color: '#cbd5e1' }}>Sliding-Window Statistical Health:</div>
                  <div style={{ color: '#f59e0b', margin: '4px 0' }}>Hourly Velocity: 24 req/h | Z-score: +3.42 (|Z| &gt; 3.00)</div>
                  <div style={{ color: '#38bdf8' }}>Cross-System Audit: Shopify ERP &lt;=&gt; Local Database</div>
                  <div style={{ color: '#10b981', marginTop: '4px' }}>Reconciliation: MATCHED (0 orphan records)</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b' }}>IQR OUTLIER FENCE</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>1.5 x IQR</div>
                  </div>
                  <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b' }}>LEDGER DRIFT</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>0.00%</div>
                  </div>
                </div>
              </>
            )}

            {activeTourTab === 3 && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                    SECURITY : ADVERSARIAL MATRIX &amp; DLP
                  </span>
                  <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#f43f5e' }}>
                    38/40 Blocked
                  </span>
                </div>
                <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '0.76rem' }}>
                  <div style={{ color: '#cbd5e1' }}>OWASP Attack Vectors Tested:</div>
                  <div style={{ color: '#10b981', margin: '4px 0' }}>[PASS] LLM01: Prompt Injection / System Override</div>
                  <div style={{ color: '#10b981', marginBottom: '4px' }}>[PASS] LLM02: Sensitive Data Exfiltration (DLP)</div>
                  <div style={{ color: '#10b981' }}>[PASS] Verhoeff Algorithm: Indian Aadhaar &amp; PAN</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b' }}>ATTACK TESTS</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>40 Scenarios</div>
                  </div>
                  <div style={{ background: '#0b0e14', border: '1px solid #1c2331', borderRadius: '4px', padding: '10px' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748b' }}>AUTOMATED DEFENSE</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>95.0%</div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          6. WHY ARGVTIX (Comparison Table)
         ────────────────────────────────────────────────────────────────────────── */}
      <section id="comparison" style={{ borderTop: '1px solid #1a1e29', borderBottom: '1px solid #1a1e29', background: '#090b10', padding: '72px 24px' }}>
        <div style={{ maxWidth: '1240px', margin: '0 auto' }}>
          {/* Header */}
          <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 36px' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
              WHY ARGVTIX
            </div>
            <h2 style={{ fontSize: '2.2rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.025em', margin: '0 0 12px' }}>
              Why Passive Tracing is Not Enough for AI Agents
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '0.94rem', margin: 0, lineHeight: 1.6 }}>
              Standard logging tools record errors after money has already been sent or a database has been corrupted.
              Argvtix stops violations before they happen.
            </p>
          </div>

          {/* Symmetrical Table */}
          <div
            style={{
              background: '#0d111a',
              border: '1px solid #212635',
              borderRadius: '8px',
              overflow: 'hidden',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ background: '#080a0f', borderBottom: '1px solid #1f2738' }}>
                  <th style={{ padding: '16px 20px', color: '#64748b', fontWeight: 700, width: '28%' }}>WHAT YOUR TEAM NEEDS</th>
                  <th style={{ padding: '16px 20px', color: '#94a3b8', fontWeight: 600, width: '36%' }}>PASSIVE LOGGING TOOLS (LangSmith / Helicone)</th>
                  <th style={{ padding: '16px 20px', color: '#10b981', fontWeight: 700, width: '36%' }}>ARGVTIX ACTIVE GUARD</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid #161b26' }}>
                  <td style={{ padding: '16px 20px', fontWeight: 600, color: '#f8fafc' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Lock size={16} color="#38bdf8" />
                      <span>Stop Bad Actions Before They Happen</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <X size={15} color="#64748b" />
                      <span>None (Only logs errors after damage is done)</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#10b981', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={15} color="#10b981" />
                      <span>Tool Gateway blocks actions before SQL commit</span>
                    </div>
                  </td>
                </tr>

                <tr style={{ borderBottom: '1px solid #161b26' }}>
                  <td style={{ padding: '16px 20px', fontWeight: 600, color: '#f8fafc' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Database size={16} color="#38bdf8" />
                      <span>Check AI Words Against Real Database</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <X size={15} color="#64748b" />
                      <span>None (Only inspects chatbot text messages)</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#10b981', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={15} color="#10b981" />
                      <span>Mathematical SQL diff vs propositional claims</span>
                    </div>
                  </td>
                </tr>

                <tr style={{ borderBottom: '1px solid #161b26' }}>
                  <td style={{ padding: '16px 20px', fontWeight: 600, color: '#f8fafc' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Layers size={16} color="#38bdf8" />
                      <span>Spending Limits &amp; Human Approval</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <X size={15} color="#64748b" />
                      <span>Not supported</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#10b981', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={15} color="#10b981" />
                      <span>Automatic routing to human manager with 1-click approve</span>
                    </div>
                  </td>
                </tr>

                <tr style={{ borderBottom: '1px solid #161b26' }}>
                  <td style={{ padding: '16px 20px', fontWeight: 600, color: '#f8fafc' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Activity size={16} color="#38bdf8" />
                      <span>Reliability Metric (Handling Flakiness)</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <X size={15} color="#64748b" />
                      <span>pass@k (Hides failure if any 1 out of 5 runs worked)</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#10b981', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={15} color="#10b981" />
                      <span>Strict pass^k (Requires 100% of all test runs to succeed)</span>
                    </div>
                  </td>
                </tr>

                <tr style={{ borderBottom: '1px solid #161b26' }}>
                  <td style={{ padding: '16px 20px', fontWeight: 600, color: '#f8fafc' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FileText size={16} color="#38bdf8" />
                      <span>Shopify ERP &amp; Salesforce Sync</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <X size={15} color="#64748b" />
                      <span>None</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#10b981', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={15} color="#10b981" />
                      <span>Automatic background ledger audit &amp; reconciliation</span>
                    </div>
                  </td>
                </tr>

                <tr>
                  <td style={{ padding: '16px 20px', fontWeight: 600, color: '#f8fafc' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Lock size={15} color="#38bdf8" />
                      <span>Privacy &amp; Self-Hosting</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <X size={15} color="#64748b" />
                      <span>Sends all prompts to third-party multi-tenant cloud</span>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px', color: '#10b981', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={15} color="#10b981" />
                      <span>100% Air-Gapped Self-Hosted Docker (Zero data leaves you)</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          7. VERIFIED BENCHMARKS (No Fake Metrics)
         ────────────────────────────────────────────────────────────────────────── */}
      <section id="benchmarks" style={{ maxWidth: '1240px', margin: '0 auto', padding: '72px 24px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 36px' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
            VERIFIED BENCHMARKS
          </div>
          <h2 style={{ fontSize: '2.2rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.025em', margin: '0 0 12px' }}>
            Real Engineering Numbers
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.94rem', margin: 0 }}>
            Directly measured on the Argvtix engine across 80 golden benchmark test cases.
          </p>
        </div>

        {/* 4 Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
          <div className="hover-card-elevate hover-glow-emerald" style={{ padding: '24px', background: '#0d111a', border: '1px solid #1f2535', borderTop: '3px solid #10b981', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700 }}>SPEED OVERHEAD (P95)</div>
            <div style={{ fontSize: '2.1rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)', margin: '8px 0 4px' }}>
              1.32 ms
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Extremely fast check without slowing down users</div>
          </div>

          <div className="hover-card-elevate hover-glow-emerald" style={{ padding: '24px', background: '#0d111a', border: '1px solid #1f2535', borderTop: '3px solid #f8fafc', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700 }}>AUTOMATED TEST PASS RATE</div>
            <div style={{ fontSize: '2.1rem', fontWeight: 800, color: '#f8fafc', fontFamily: 'var(--font-mono)', margin: '8px 0 4px' }}>
              328 / 328
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>100% test pass across all safety rules with zero flakiness</div>
          </div>

          <div className="hover-card-elevate hover-glow-blue" style={{ padding: '24px', background: '#0d111a', border: '1px solid #1f2535', borderTop: '3px solid #38bdf8', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700 }}>MULTILINGUAL TEST SUITE</div>
            <div style={{ fontSize: '2.1rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)', margin: '8px 0 4px' }}>
              80 Cases
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>35 English, 20 Hindi Devanagari, 25 Hinglish cases</div>
          </div>

          <div className="hover-card-elevate hover-glow-rose" style={{ padding: '24px', background: '#0d111a', border: '1px solid #1f2535', borderTop: '3px solid #f43f5e', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700 }}>SECURITY STRESS TESTS</div>
            <div style={{ fontSize: '2.1rem', fontWeight: 800, color: '#f43f5e', fontFamily: 'var(--font-mono)', margin: '8px 0 4px' }}>
              40 Attacks
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>OWASP prompt injections, jailbreaks, and PII leaks tested</div>
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          7.5 FREQUENTLY ASKED QUESTIONS (FAQ) & TECHNICAL CLARIFICATIONS
         ────────────────────────────────────────────────────────────────────────── */}
      <section id="faq" style={{ maxWidth: '960px', margin: '0 auto', padding: '80px 24px' }}>
        <div style={{ textAlign: 'center', marginBottom: '48px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '999px',
              background: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid rgba(59, 130, 246, 0.25)',
              color: '#60a5fa',
              fontSize: '0.76rem',
              fontWeight: 600,
              marginBottom: '12px',
            }}
          >
            <HelpCircle size={13} />
            <span>ARCHITECTURE &amp; DEPLOYMENT FAQ</span>
          </div>

          <h2 style={{ fontSize: '2.2rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.025em', margin: '0 0 12px' }}>
            Frequently Asked Questions
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.96rem', margin: 0, maxWidth: '640px', marginInline: 'auto' }}>
            Engineering specifics regarding deterministic invariant checking, latency boundaries, and compliance isolation.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
            gap: '16px',
            alignItems: 'start',
          }}
        >
          {faqs.map((faq, index) => {
            const isOpen = openFaqIndex === index;
            const qNum = index + 1;
            return (
              <div
                key={index}
                className="hover-card-elevate"
                style={{
                  background: '#0d111a',
                  border: `1px solid ${isOpen ? '#3b82f6' : '#1e2535'}`,
                  borderRadius: '10px',
                  overflow: 'hidden',
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                  boxShadow: isOpen ? '0 8px 24px -4px rgba(59, 130, 246, 0.15)' : 'none',
                }}
              >
                <button
                  type="button"
                  onClick={() => setOpenFaqIndex(isOpen ? null : index)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setOpenFaqIndex(isOpen ? null : index);
                    }
                  }}
                  aria-expanded={isOpen}
                  aria-label={`Question ${qNum}: ${faq.question}`}
                  style={{
                    width: '100%',
                    padding: '18px 20px',
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: '12px',
                    background: 'transparent',
                    border: 'none',
                    color: '#f8fafc',
                    fontSize: '0.94rem',
                    fontWeight: 600,
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                    <span
                      style={{
                        padding: '2px 7px',
                        background: isOpen ? 'rgba(59, 130, 246, 0.2)' : 'rgba(148, 163, 184, 0.1)',
                        color: isOpen ? '#60a5fa' : '#94a3b8',
                        borderRadius: '4px',
                        fontSize: '0.72rem',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        flexShrink: 0,
                        marginTop: '2px',
                      }}
                    >
                      Q{qNum}
                    </span>
                    <span style={{ lineHeight: 1.45, color: isOpen ? '#ffffff' : '#f1f5f9' }}>{faq.question}</span>
                  </div>
                  <div
                    style={{
                      transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s ease',
                      color: isOpen ? '#60a5fa' : '#64748b',
                      flexShrink: 0,
                      marginTop: '2px',
                    }}
                  >
                    <ChevronDown size={17} />
                  </div>
                </button>

                {isOpen && (
                  <div
                    className="animate-fade-in-down"
                    style={{
                      padding: '0 20px 20px 45px',
                      color: '#94a3b8',
                      fontSize: '0.88rem',
                      lineHeight: 1.65,
                      borderTop: '1px solid #161c29',
                      paddingTop: '14px',
                    }}
                  >
                    {faq.answer}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div
          style={{
            marginTop: '36px',
            textAlign: 'center',
            fontSize: '0.86rem',
            color: '#64748b',
          }}
        >
          Have questions about your specific agent stack?{' '}
          <Link to="/contact" style={{ color: '#38bdf8', textDecoration: 'none', fontWeight: 600 }}>
            Schedule an enterprise architecture review with our team &rarr;
          </Link>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          8. PRODUCTION CTA & QUICK START
         ────────────────────────────────────────────────────────────────────────── */}
      <section style={{ borderTop: '1px solid #1a1e29', background: '#090c12', padding: '72px 24px' }}>
        <div style={{ maxWidth: '820px', margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{ fontSize: '2.3rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.025em', margin: '0 0 14px' }}>
            Start Protecting Your AI Agents Today
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.98rem', margin: '0 0 32px', lineHeight: 1.6 }}>
            Run Argvtix locally in minutes with Docker Compose or schedule a custom architecture consultation for private VPC deployment.
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <Link
              to="/contact"
              className="btn-action-primary"
              style={{ padding: '12px 26px', fontSize: '0.92rem' }}
            >
              <span>Schedule Enterprise Demo</span>
              <ArrowRight size={15} />
            </Link>

            <button
              onClick={() => setIsAuthModalOpen(true)}
              className="btn-action-secondary"
              style={{ padding: '12px 24px', fontSize: '0.92rem' }}
            >
              <span>Sign In with Work Email</span>
              <ArrowRight size={15} />
            </button>

            <Link
              to="/overview"
              className="btn-action-secondary"
              style={{ padding: '12px 24px', fontSize: '0.92rem' }}
            >
              <span>Launch Observability Console</span>
              <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────────────────────
          9. MULTI-COLUMN ENTERPRISE FOOTER
         ────────────────────────────────────────────────────────────────────────── */}
      <footer style={{ borderTop: '1px solid #161b26', background: '#06070a', padding: '56px 32px 36px' }}>
        <div style={{ maxWidth: '1240px', margin: '0 auto', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: '48px', marginBottom: '44px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <ArgvtixLogo size={28} showBadge={false} />
            </div>
            <p style={{ fontSize: '0.82rem', color: '#64748b', lineHeight: 1.6, maxWidth: '340px', margin: 0 }}>
              Runtime safety guard, truth verifier, and continuous ledger audit for enterprise AI agents.
            </p>
            <div style={{ marginTop: '16px', fontSize: '0.72rem', color: '#475569', fontFamily: 'var(--font-mono)' }}>
              Status: Gateway Online (127.0.0.1:8000)
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#cbd5e1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '14px' }}>
              PLATFORM CONSOLE
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.82rem' }}>
              <Link to="/overview" style={{ color: '#94a3b8', textDecoration: 'none' }}>Overview Console</Link>
              <Link to="/traces" style={{ color: '#94a3b8', textDecoration: 'none' }}>Trace Waterfall</Link>
              <Link to="/guard" style={{ color: '#94a3b8', textDecoration: 'none' }}>Action Guard &amp; Approvals</Link>
              <Link to="/evals" style={{ color: '#94a3b8', textDecoration: 'none' }}>Truth Verifier</Link>
              <Link to="/watchdog" style={{ color: '#94a3b8', textDecoration: 'none' }}>State Watchdog</Link>
              <Link to="/security" style={{ color: '#94a3b8', textDecoration: 'none' }}>Red Team Matrix</Link>
              <Link to="/benchmark" style={{ color: '#94a3b8', textDecoration: 'none' }}>Model Benchmarks</Link>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#cbd5e1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '14px' }}>
              DEVELOPERS &amp; DEMOS
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.82rem' }}>
              <Link to="/contact" style={{ color: '#60a5fa', textDecoration: 'none', fontWeight: 600 }}>
                Request Architecture Demo
              </Link>
              <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer" style={{ color: '#94a3b8', textDecoration: 'none' }}>
                OpenAPI / Swagger
              </a>
              <a href="http://127.0.0.1:8000/health" target="_blank" rel="noreferrer" style={{ color: '#94a3b8', textDecoration: 'none' }}>
                Health Check API
              </a>
              <span style={{ color: '#64748b' }}>Python SDK (v1.2)</span>
              <span style={{ color: '#64748b' }}>MCP Proxy Adapter</span>
              <span style={{ color: '#64748b' }}>Docker Compose Prod</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#cbd5e1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '14px' }}>
              LEGAL &amp; PRIVACY
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.82rem' }}>
              <Link to="/privacy-policy" style={{ color: '#94a3b8', textDecoration: 'none' }}>Privacy Policy</Link>
              <Link to="/terms" style={{ color: '#94a3b8', textDecoration: 'none' }}>Terms of Service</Link>
              <Link to="/contact" style={{ color: '#94a3b8', textDecoration: 'none' }}>Security Disclosures</Link>
              <button
                type="button"
                onClick={() => window.dispatchEvent(new Event('argvtix-open-cookie-settings'))}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  textAlign: 'left',
                  cursor: 'pointer',
                  padding: 0,
                  fontSize: '0.82rem',
                }}
              >
                Cookie Preferences
              </button>
              <span style={{ color: '#64748b' }}>DPDP Act 2023 Compliant</span>
              <span style={{ color: '#64748b' }}>Zero Model Training Guarantee</span>
              <span style={{ color: '#64748b' }}>SOC 2 Type II Architecture</span>
            </div>
          </div>
        </div>

        <div style={{ maxWidth: '1240px', margin: '0 auto', borderTop: '1px solid #141822', paddingTop: '22px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: '#475569', flexWrap: 'wrap', gap: '10px' }}>
          <span>© 2026 Argvtix Technologies Inc. All rights reserved.</span>
          <span>Zero-bypass deterministic AI reliability infrastructure.</span>
        </div>
      </footer>

      {/* ──────────────────────────────────────────────────────────────────────────
          10. EMAIL + OTP REGISTRATION / SIGN-IN MODAL
         ────────────────────────────────────────────────────────────────────────── */}
      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </div>
  );
};
