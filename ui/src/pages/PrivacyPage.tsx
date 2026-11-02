import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, ArrowLeft, Lock, EyeOff, Server } from 'lucide-react';
import { usePageMetadata } from '../hooks/usePageMetadata';

export const PrivacyPage: React.FC = () => {
  usePageMetadata({
    title: 'Privacy Policy & Data Protection | Argvtix',
    description:
      'Argvtix privacy commitments, DPDP Act 2023 compliance, zero model training guarantee, and data processing terms for enterprise AI reliability.',
    canonicalUrl: 'https://argvtix.ai/privacy-policy',
  });

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-canvas)', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>
      {/* Top Header */}
      <header
        style={{
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-surface)',
          padding: '16px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link
            to="/"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: 'var(--text-secondary)',
              textDecoration: 'none',
              fontSize: '0.82rem',
              fontWeight: 500,
            }}
          >
            <ArrowLeft size={14} />
            <span>Back to Home</span>
          </Link>
          <span style={{ color: 'var(--border-default)' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '22px',
                height: '22px',
                borderRadius: '4px',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#3b82f6',
              }}
            >
              <ShieldCheck size={14} />
            </div>
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f8fafc', letterSpacing: '-0.01em' }}>
              Argvtix Legal & Compliance
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Link
            to="/terms"
            style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '0.8rem' }}
          >
            Terms of Service
          </Link>
          <Link
            to="/overview"
            className="btn btn-primary btn-sm"
            style={{ textDecoration: 'none' }}
          >
            Console
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ maxWidth: '860px', margin: '0 auto', padding: '48px 24px 80px' }}>
        <div style={{ marginBottom: '32px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#3b82f6', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px' }}>
            Enterprise Data Protection & Privacy Architecture
          </div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em', margin: 0 }}>
            Privacy Policy
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '8px' }}>
            Effective Date: January 1, 2026. Version 2.4. Applicable to self-hosted, cloud-managed, and hybrid deployments.
          </p>
        </div>

        {/* Core Principles Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '40px' }}>
          <div style={{ padding: '16px', background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', marginBottom: '8px' }}>
              <Lock size={16} />
              <strong style={{ fontSize: '0.85rem' }}>Zero Model Training</strong>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              Customer prompts, tool inputs, and database records are never used to train or fine-tune public foundation models.
            </p>
          </div>

          <div style={{ padding: '16px', background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#0ea5e9', marginBottom: '8px' }}>
              <EyeOff size={16} />
              <strong style={{ fontSize: '0.85rem' }}>Deterministic PII Masking</strong>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              Indian and international PII (Aadhaar, PAN, phone numbers, credit card tokens) is sanitized before entering model context.
            </p>
          </div>

          <div style={{ padding: '16px', background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#3b82f6', marginBottom: '8px' }}>
              <Server size={16} />
              <strong style={{ fontSize: '0.85rem' }}>VPC & Air-Gapped Ready</strong>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              Runs fully inside customer infrastructure with zero external telemetry phoning home.
            </p>
          </div>
        </div>

        {/* Detailed Sections */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', lineHeight: 1.6, fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              1. Information Ingestion & Scope
            </h2>
            <p>
              Argvtix operates as an infrastructure proxy layer positioned between autonomous LLM agents and backend systems of record.
              In this role, Argvtix inspects:
            </p>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li><strong>Agent Execution Traces:</strong> Natural language prompts, system instructions, and completion strings.</li>
              <li><strong>Tool Call Payloads:</strong> Tool names, parameter JSON arguments, and execution return values.</li>
              <li><strong>Database State Snapshots:</strong> Entity attributes queried to verify claim grounding (e.g., order status, balance).</li>
              <li><strong>Telemetry Metadata:</strong> Latency metrics, token usage counters, and HTTP status codes.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              2. On-Premise Execution & Self-Hosting Isolation
            </h2>
            <p>
              When deployed using Docker, Kubernetes, or source builds, Argvtix processes all telemetry locally within your VPC.
              No transaction data, customer identities, or invariant logs are transmitted to Argvtix Technologies Inc.
              Telemetry data remains persisted in your configured SQLite or PostgreSQL database instance.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              3. Data Loss Prevention (DLP) & PII Sanitization
            </h2>
            <p>
              Argvtix includes a deterministic Layer 1 DLP filter. Before prompt payloads or tool outputs leave your network boundary:
            </p>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li>Aadhaar numbers are validated using the Verhoeff algorithm and replaced with <code>[AADHAAR_REDACTED]</code>.</li>
              <li>Permanent Account Number (PAN) values are matched against 5-letter, 4-digit, 1-letter patterns and masked.</li>
              <li>Payment card CVVs, bearer auth tokens, and private SSH keys are intercepted and blocked on the hot path.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              4. Data Retention & Ephemeral Purging
            </h2>
            <p>
              Execution trace data is stored ephemerally according to your organization's retention policy (default: 30 days).
              Audit logs for Human-in-the-Loop approval events are maintained with cryptographic hashes to satisfy financial compliance mandates.
              Operators can execute automated TTL purging using the provided database migration commands.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              5. Regulatory Compliance
            </h2>
            <p>
              Argvtix is engineered to comply with:
            </p>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li><strong>India Digital Personal Data Protection (DPDP) Act 2023:</strong> Enforces data fiduciary obligations and automated PII protection.</li>
              <li><strong>EU General Data Protection Regulation (GDPR):</strong> Complies with Article 25 (Data Protection by Design and by Default) and Article 32 (Security of Processing).</li>
              <li><strong>SOC 2 Type II Readiness:</strong> Provides immutable append-only audit logs for all security-relevant interventions.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              6. Cookies &amp; Local Storage Practices
            </h2>
            <p>
              Argvtix maintains a zero-advertising policy. We never deploy third-party advertising cookies, cross-site trackers, or behavioral profiling beacons.
            </p>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li><strong>Strictly Necessary Storage:</strong> LocalStorage keys (e.g. <code>argvtix_auth_token</code>, <code>argvtix_user</code>) are utilized solely to authenticate authorized operational sessions and prevent unauthorized access.</li>
              <li><strong>Optional Telemetry:</strong> Anonymized interaction event counters are recorded only when explicitly enabled by the user.</li>
            </ul>
            <div style={{ marginTop: '14px' }}>
              <button
                type="button"
                onClick={() => window.dispatchEvent(new Event('argvtix-open-cookie-settings'))}
                className="btn-action-secondary"
                style={{ padding: '6px 14px', fontSize: '0.78rem' }}
              >
                Manage Cookie &amp; Privacy Preferences
              </button>
            </div>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              7. User Privacy Rights &amp; Data Subject Requests
            </h2>
            <p>
              In accordance with the India DPDP Act 2023, EU GDPR, and applicable enterprise privacy frameworks, users and operational administrators hold the following rights:
            </p>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li><strong>Right of Access &amp; Summary:</strong> Request an export of any personal identifiers or audit logs associated with your account.</li>
              <li><strong>Right to Correction &amp; Erasure:</strong> Request immediate correction of outdated records or deletion of non-essential account profiles.</li>
              <li><strong>Grievance Redressal:</strong> Submit formal privacy inquiries directly to our designated Data Protection Officer at <code>dpo@argvtix.internal</code>. All inquiries are acknowledged within 48 business hours.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              8. Policy Updates &amp; Versioning
            </h2>
            <p>
              We periodically update this policy to reflect new security invariants, statutory updates, and architectural changes. Revisions are published with an updated version number and effective timestamp. Material modifications will be flagged in the platform console.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              9. Security &amp; Infrastructure Contact
            </h2>
            <p>
              For security advisories, vulnerability disclosures, or enterprise Data Processing Agreements (DPA), contact:
              <br />
              <code style={{ color: '#f8fafc', fontFamily: 'var(--font-mono)', fontSize: '0.82rem', marginTop: '6px', display: 'inline-block' }}>
                privacy@argvtix.internal • security@argvtix.internal
              </code>
            </p>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border-default)', padding: '24px 32px', textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px', flexWrap: 'wrap' }}>
          <span>© 2026 Argvtix Technologies Inc. All rights reserved.</span>
          <Link to="/contact" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>Contact &amp; Support</Link>
          <Link to="/terms" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>Terms of Service</Link>
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event('argvtix-open-cookie-settings'))}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: '0.78rem', cursor: 'pointer', padding: 0 }}
          >
            Cookie Preferences
          </button>
        </div>
      </footer>
    </div>
  );
};
