import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CheckCircle2, ArrowRight, ShieldCheck, LayoutDashboard, Clock } from 'lucide-react';
import { usePageMetadata } from '../hooks/usePageMetadata';

interface ThankYouState {
  submissionId?: string;
  name?: string;
  email?: string;
  company?: string;
}

export const ThankYouPage: React.FC = () => {
  usePageMetadata({
    title: 'Request Confirmed — Thank You | Argvtix',
    description:
      'Your request for an enterprise architecture review and demonstration has been received. Our team will contact you within 24 business hours.',
    canonicalUrl: 'https://argvtix.ai/thank-you',
  });

  const location = useLocation();
  const state = (location.state as ThankYouState) || {};

  const submissionId = state.submissionId || 'PL-DEMO-CONFIRMED';
  const recipientName = state.name ? state.name.split(' ')[0] : 'there';

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
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none' }}>
          <div
            style={{
              width: '24px',
              height: '24px',
              borderRadius: '6px',
              background: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#3b82f6',
            }}
          >
            <ShieldCheck size={14} />
          </div>
          <span style={{ fontWeight: 700, fontSize: '0.94rem', color: '#f8fafc', letterSpacing: '-0.01em' }}>
            Argvtix
          </span>
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Link
            to="/console"
            style={{
              fontSize: '0.82rem',
              color: 'var(--text-secondary)',
              textDecoration: 'none',
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border-default)',
              background: 'var(--bg-elevated)',
            }}
          >
            Open Console
          </Link>
        </div>
      </header>

      {/* Main Confirmation Content */}
      <main style={{ maxWidth: '720px', margin: '64px auto', padding: '0 24px' }}>
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-default)',
            borderRadius: '16px',
            padding: '48px 40px',
            boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
            textAlign: 'center',
          }}
        >
          {/* Animated Success Badge */}
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#10b981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px auto',
            }}
          >
            <CheckCircle2 size={36} />
          </div>

          <h1
            style={{
              fontSize: '2rem',
              fontWeight: 800,
              letterSpacing: '-0.025em',
              color: '#f8fafc',
              marginBottom: '12px',
            }}
          >
            Demo & Review Request Confirmed
          </h1>

          <p
            style={{
              fontSize: '1rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
              maxWidth: '560px',
              margin: '0 auto 28px auto',
            }}
          >
            Thank you, <strong style={{ color: '#f1f5f9' }}>{recipientName}</strong>. Your architecture consultation request for{' '}
            {state.company ? <strong style={{ color: '#f1f5f9' }}>{state.company}</strong> : 'your organization'} has been logged in our secure ticketing system.
          </p>

          {/* Reference Pill */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 14px',
              borderRadius: '8px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              color: '#94a3b8',
              marginBottom: '36px',
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>Reference ID:</span>
            <span style={{ color: '#60a5fa', fontWeight: 600 }}>{submissionId}</span>
          </div>

          {/* Timeline / Next Steps Card */}
          <div
            style={{
              background: 'var(--bg-canvas)',
              border: '1px solid var(--border-default)',
              borderRadius: '12px',
              padding: '24px',
              textAlign: 'left',
              marginBottom: '36px',
            }}
          >
            <h2
              style={{
                fontSize: '0.88rem',
                fontWeight: 700,
                color: '#f1f5f9',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <Clock size={15} style={{ color: '#3b82f6' }} />
              <span>What Happens Next (24-Hour SLA)</span>
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <span
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-default)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    color: '#60a5fa',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  1
                </span>
                <div>
                  <div style={{ fontSize: '0.86rem', fontWeight: 600, color: '#f1f5f9' }}>
                    Architectural Assessment
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                    Our core systems engineering team reviews your AI agent tool execution model and policy enforcement requirements.
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <span
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-default)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    color: '#60a5fa',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  2
                </span>
                <div>
                  <div style={{ fontSize: '0.86rem', fontWeight: 600, color: '#f1f5f9' }}>
                    Technical Working Session
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                    We provide a direct calendar invitation with mutual NDA for a live 30-minute demonstration tailored to your exact tech stack.
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <span
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-default)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    color: '#60a5fa',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  3
                </span>
                <div>
                  <div style={{ fontSize: '0.86rem', fontWeight: 600, color: '#f1f5f9' }}>
                    Private Sandbox Access
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                    You receive VPC-ready Helm charts or docker-compose manifests to test the Action Guard gateway locally on your staging clusters.
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Action CTAs */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '14px', flexWrap: 'wrap' }}>
            <Link
              to="/console"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                borderRadius: '6px',
                background: '#2563eb',
                color: '#ffffff',
                textDecoration: 'none',
                fontSize: '0.88rem',
                fontWeight: 600,
              }}
            >
              <LayoutDashboard size={15} />
              <span>Explore Interactive Console</span>
              <ArrowRight size={14} />
            </Link>

            <Link
              to="/"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '6px',
                border: '1px solid var(--border-default)',
                background: 'var(--bg-elevated)',
                color: 'var(--text-secondary)',
                textDecoration: 'none',
                fontSize: '0.88rem',
                fontWeight: 500,
              }}
            >
              <span>Return to Home</span>
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
};
