import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Home, Terminal, ShieldAlert } from 'lucide-react';
import { ProoflineLogo } from '../components/ProoflineLogo';
import { usePageMetadata } from '../hooks/usePageMetadata';

export const NotFoundPage: React.FC = () => {
  usePageMetadata({
    title: '404 Page Not Found | Proofline AI Reliability',
    description:
      'The requested resource was not found. Return to the Proofline homepage or explore the platform console.',
  });
  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#08090d',
        color: '#f8fafc',
        fontFamily: 'var(--font-sans)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Top Header */}
      <header
        style={{
          borderBottom: '1px solid #1a202c',
          background: 'rgba(8, 9, 13, 0.94)',
          backdropFilter: 'blur(16px)',
          padding: '0 32px',
          height: '68px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}>
          <ProoflineLogo size={30} version="v1.2.0-prod" />
        </Link>
        <Link
          to="/"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: '#94a3b8',
            textDecoration: 'none',
            fontSize: '0.84rem',
            fontWeight: 500,
          }}
        >
          <ArrowLeft size={14} />
          <span>Return to Homepage</span>
        </Link>
      </header>

      {/* Main 404 Hero Container */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 24px',
        }}
      >
        <div
          style={{
            maxWidth: '640px',
            width: '100%',
            textAlign: 'center',
            background: '#0d111a',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '10px',
            padding: '48px 36px',
            boxShadow: '0 24px 64px rgba(0, 0, 0, 0.6)',
          }}
        >
          {/* Eyebrow Badge */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 12px',
              borderRadius: '4px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              color: '#ef4444',
              fontSize: '0.74rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: '20px',
            }}
          >
            <ShieldAlert size={14} />
            <span>ERR_ROUTE_NOT_FOUND (HTTP 404)</span>
          </div>

          <h1
            style={{
              fontSize: '2.5rem',
              fontWeight: 800,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              margin: '0 0 16px',
            }}
          >
            Page Not Found
          </h1>

          <p
            style={{
              fontSize: '0.94rem',
              color: '#94a3b8',
              lineHeight: 1.6,
              margin: '0 auto 28px',
              maxWidth: '480px',
            }}
          >
            The requested destination or invariant resource does not exist on this Proofline cluster.
            The route may have been decommissioned or moved to an authenticated console path.
          </p>

          {/* Quick Action Navigation Grid */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '32px' }}>
            <Link
              to="/"
              className="btn-action-primary"
              style={{ padding: '10px 20px', fontSize: '0.86rem' }}
            >
              <Home size={15} />
              <span>Back to Homepage</span>
            </Link>

            <Link
              to="/overview"
              className="btn-action-secondary"
              style={{ padding: '10px 20px', fontSize: '0.86rem' }}
            >
              <Terminal size={15} />
              <span>Open Console</span>
            </Link>
          </div>

          {/* Diagnostic Code Box */}
          <div
            style={{
              background: '#08090d',
              border: '1px solid #1e2638',
              borderRadius: '6px',
              padding: '12px 16px',
              textAlign: 'left',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.76rem',
              color: '#64748b',
              lineHeight: 1.5,
            }}
          >
            <div style={{ color: '#94a3b8', fontWeight: 600, marginBottom: '4px' }}>Diagnostic Trace:</div>
            <div>STATUS: 404_NOT_FOUND</div>
            <div>INGRESS_PROXY: PROOFLINE_TOOL_GATEWAY</div>
            <div>RESOLUTION: Check route URI or authenticate to access privileged console spaces.</div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          borderTop: '1px solid #1a202c',
          padding: '20px 32px',
          textAlign: 'center',
          fontSize: '0.78rem',
          color: '#64748b',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px', flexWrap: 'wrap' }}>
          <span>© 2026 Proofline Technologies Inc.</span>
          <Link to="/contact" style={{ color: '#94a3b8', textDecoration: 'none' }}>Contact Support</Link>
          <Link to="/privacy-policy" style={{ color: '#94a3b8', textDecoration: 'none' }}>Privacy Policy</Link>
          <Link to="/terms" style={{ color: '#94a3b8', textDecoration: 'none' }}>Terms of Service</Link>
        </div>
      </footer>
    </div>
  );
};
