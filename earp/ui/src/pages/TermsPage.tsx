import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Scale } from 'lucide-react';
import { usePageMetadata } from '../hooks/usePageMetadata';

export const TermsPage: React.FC = () => {
  usePageMetadata({
    title: 'Terms of Service | Proofline Enterprise AI Reliability',
    description:
      'Terms of service, enterprise licensing agreements, runtime policy liability limits, and API usage conditions for Proofline.',
    canonicalUrl: 'https://proofline.ai/terms',
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
              <Scale size={14} />
            </div>
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f8fafc', letterSpacing: '-0.01em' }}>
              Proofline Legal & Compliance
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Link
            to="/privacy"
            style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '0.8rem' }}
          >
            Privacy Policy
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
            Enterprise Software License & Service Agreement
          </div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em', margin: 0 }}>
            Terms of Service
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '8px' }}>
            Effective Date: January 1, 2026. Version 2.4. Governs production usage of Proofline Tool Gateway, Claim Verifier, and Watchdog.
          </p>
        </div>

        {/* Detailed Sections */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', lineHeight: 1.6, fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              1. Acceptance & Infrastructure Scope
            </h2>
            <p>
              By installing, self-hosting, or accessing Proofline (EARP - Enterprise AI Reliability Platform), you agree to these Terms of Service.
              Proofline provides deterministic runtime boundary enforcement, semantic claim grounding, and asynchronous state reconciliation.
              If you are integrating Proofline on behalf of an enterprise entity, you warrant that you hold authorized administrative credentials.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              2. Autonomous Agent Liability & Authorization Boundary
            </h2>
            <p>
              Proofline executes strictly as an invariant gatekeeper and proxy filter. Proofline does not generate autonomous business decisions on its own accord.
              The customer remains solely responsible for:
            </p>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li>Configuring suitable invariant thresholds (e.g., maximum autonomous refund amounts, velocity limits).</li>
              <li>Supervising Human-in-the-Loop (HITL) approval requests executed by operational personnel.</li>
              <li>Connecting valid API credentials to downstream Model Context Protocol (MCP) tool servers.</li>
              <li>Validating database connection credentials and rollback privileges.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              3. Upstream Foundation Model Disclaimers
            </h2>
            <p>
              Proofline is designed to mitigate hallucinations, unintended side effects, and adversarial prompt injections from upstream LLM providers (including OpenAI, Google, Anthropic, or open-source weights).
              However, foundation models exhibit non-deterministic behavior. Proofline guarantees deterministic enforcement of configured policy code, but does not warrant that upstream models will generate grammatically correct or contextually optimal natural language.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              4. Custom Domain & Self-Hosting Licensing
            </h2>
            <p>
              Customers are permitted to bind custom domain names (e.g., <code>app.yourdomain.com</code>) to self-hosted instances of Proofline using Caddy, Nginx, or cloud ingress controllers.
              Redistribution, reselling, or white-labeling Proofline as a competing standalone service without commercial licensing is prohibited.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              5. Service Availability & Production SLAs
            </h2>
            <p>
              For enterprise managed clusters, Proofline commits to a 99.95% availability SLA for the Layer 1 Tool Gateway.
              For self-hosted community installations, availability depends on customer infrastructure reliability, underlying SQLite/Postgres disk I/O, and host network availability.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              6. Limitation of Liability
            </h2>
            <p>
              To the maximum extent permitted by applicable law, Proofline Technologies Inc. shall not be liable for indirect, incidental, or consequential damages resulting from upstream model hallucinations or erroneous human supervisor authorizations executed through the Tool Gateway console.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              7. Acceptable Use Policy &amp; Security Testing
            </h2>
            <p>
              Proofline provides an adversarial Red Team evaluation harness for internal security hardening. Users agree not to:
            </p>
            <ul style={{ paddingLeft: '20px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li>Deploy Proofline to facilitate unauthorized penetration testing against third-party systems without documented consent.</li>
              <li>Attempt to reverse-engineer or tamper with cryptographic audit chain signatures generated by the Watchdog module.</li>
              <li>Circumvent rate limiting or multi-tenant isolation mechanisms within hosted cluster environments.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              8. Termination of Access
            </h2>
            <p>
              Proofline reserves the right to revoke API token access or terminate hosted cluster instances if malicious exploitation, credential compromise, or material breach of these terms is detected.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              9. Governing Law &amp; Dispute Resolution
            </h2>
            <p>
              These terms are governed by and construed in accordance with applicable enterprise commercial law. Any disputes arising under these terms shall be resolved through binding commercial arbitration or courts of competent jurisdiction.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
              10. Inquiries &amp; Legal Notices
            </h2>
            <p>
              For contractual inquiries, enterprise support agreements, or compliance documentation:
              <br />
              <code style={{ color: '#f8fafc', fontFamily: 'var(--font-mono)', fontSize: '0.82rem', marginTop: '6px', display: 'inline-block' }}>
                legal@proofline.internal
              </code>
            </p>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border-default)', padding: '24px 32px', textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px', flexWrap: 'wrap' }}>
          <span>© 2026 Proofline Technologies Inc. All rights reserved.</span>
          <Link to="/contact" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>Contact &amp; Support</Link>
          <Link to="/privacy-policy" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>Privacy Policy</Link>
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event('proofline-open-cookie-settings'))}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: '0.78rem', cursor: 'pointer', padding: 0 }}
          >
            Cookie Preferences
          </button>
        </div>
      </footer>
    </div>
  );
};
