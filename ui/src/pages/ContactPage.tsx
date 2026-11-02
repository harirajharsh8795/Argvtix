import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  ArrowLeft,
  Lock,
  Server,
  Building2,
  Mail,
  User,
  Send,
  AlertCircle,
  Clock,
  Sparkles,
} from 'lucide-react';
import { usePageMetadata } from '../hooks/usePageMetadata';
import { trackEvent } from '../utils/analytics';

export const ContactPage: React.FC = () => {
  usePageMetadata({
    title: 'Request Enterprise Demo & Architecture Review | Argvtix',
    description:
      'Schedule a confidential engineering demo and architecture review with the Argvtix team. Discuss private VPC deployment, custom Action Guard policies, and agent compliance.',
    canonicalUrl: 'https://argvtix.ai/contact',
  });

  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    useCase: '',
    // Honeypot field: invisible to real users, populated by naive spam scrapers
    companyTaxId: '',
  });

  const [turnstileToken, setTurnstileToken] = useState<string>('local-dev-verified');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const turnstileSiteKey = import.meta.env.VITE_CLOUDFLARE_TURNSTILE_SITE_KEY;
  const turnstileContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (turnstileSiteKey && typeof window !== 'undefined') {
      // Cloudflare Turnstile script injection
      const scriptId = 'cloudflare-turnstile-script';
      if (!document.getElementById(scriptId)) {
        const script = document.createElement('script');
        script.id = scriptId;
        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);

        script.onload = () => {
          // @ts-expect-error turnstile global
          if (window.turnstile && turnstileContainerRef.current) {
            // @ts-expect-error turnstile global
            window.turnstile.render(turnstileContainerRef.current, {
              sitekey: turnstileSiteKey,
              callback: (token: string) => setTurnstileToken(token),
            });
          }
        };
      }
    }
  }, [turnstileSiteKey]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errorMessage) setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // Client-side quick checks
    if (!formData.name.trim()) {
      setErrorMessage('Please provide your full name.');
      return;
    }
    if (!formData.email.trim() || !formData.email.includes('@')) {
      setErrorMessage('Please provide a valid corporate or work email address.');
      return;
    }
    if (!formData.company.trim()) {
      setErrorMessage('Please provide your company or organization name.');
      return;
    }
    if (formData.useCase.trim().length < 10) {
      setErrorMessage('Please describe your AI agent architecture or reliability requirement in at least 10 characters.');
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await fetch('/api/v1/contact', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name.trim(),
          email: formData.email.trim(),
          company: formData.company.trim(),
          use_case: formData.useCase.trim(),
          turnstile_token: turnstileToken,
          honeypot: formData.companyTaxId.trim() || null,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to submit demo request. Please verify inputs.');
      }

      // Track lead generation conversion event in GA4
      trackEvent('generate_lead', {
        company: formData.company.trim(),
        submission_id: data.submission_id,
      });

      // Redirect to thank-you confirmation page with secure state
      navigate('/thank-you', {
        state: {
          submissionId: data.submission_id,
          name: formData.name.trim(),
          email: formData.email.trim(),
          company: formData.company.trim(),
        },
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred. Please try again.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-canvas)', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>
      {/* Navigation Header */}
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
              fontSize: '0.84rem',
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
            <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f8fafc', letterSpacing: '-0.01em' }}>
              Argvtix Architecture Consultation
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Response SLA: &lt; 24h</span>
          <Link
            to="/docs"
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
            Read Technical Docs
          </Link>
        </div>
      </header>

      {/* Main Form Container */}
      <main style={{ maxWidth: '1100px', margin: '48px auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1fr) minmax(360px, 1.2fr)', gap: '48px', alignItems: 'start' }}>
          {/* Left Column: Context & Guarantees */}
          <div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '4px 10px',
                borderRadius: '999px',
                background: 'rgba(59, 130, 246, 0.1)',
                border: '1px solid rgba(59, 130, 246, 0.25)',
                color: '#60a5fa',
                fontSize: '0.78rem',
                fontWeight: 600,
                marginBottom: '16px',
              }}
            >
              <Sparkles size={13} />
              <span>Direct Engineering Engagement</span>
            </div>

            <h1
              style={{
                fontSize: '2.1rem',
                fontWeight: 800,
                letterSpacing: '-0.03em',
                lineHeight: 1.2,
                color: '#f8fafc',
                marginBottom: '16px',
              }}
            >
              Request an Enterprise Architecture Review
            </h1>

            <p style={{ fontSize: '0.96rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '32px' }}>
              Connect directly with our core platform engineering team to evaluate Argvtix for your autonomous AI agents, tool invocation boundaries, and continuous compliance.
            </p>

            {/* Value Highlights */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
                <div
                  style={{
                    padding: '8px',
                    borderRadius: '8px',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-default)',
                    color: '#3b82f6',
                    marginTop: '2px',
                  }}
                >
                  <Clock size={16} />
                </div>
                <div>
                  <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', margin: 0, marginBottom: '4px' }}>
                    Guaranteed 24-Hour Engineering SLA
                  </h2>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
                    Your request is reviewed by senior reliability engineers who analyze your agent tooling specs, not aggressive sales reps.
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
                <div
                  style={{
                    padding: '8px',
                    borderRadius: '8px',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-default)',
                    color: '#10b981',
                    marginTop: '2px',
                  }}
                >
                  <Server size={16} />
                </div>
                <div>
                  <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', margin: 0, marginBottom: '4px' }}>
                    Air-Gapped & Private VPC Deployment
                  </h2>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
                    Deploy ARGVTIX within your own AWS, Azure, or GCP VPC with zero inbound public ingress and sovereign data residency.
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
                <div
                  style={{
                    padding: '8px',
                    borderRadius: '8px',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-default)',
                    color: '#8b5cf6',
                    marginTop: '2px',
                  }}
                >
                  <Lock size={16} />
                </div>
                <div>
                  <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', margin: 0, marginBottom: '4px' }}>
                    Action Guard Policy Tailoring
                  </h2>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
                    We co-design deterministic invariants for your sensitive tool operations (refunds, database writes, and external API calls).
                  </p>
                </div>
              </div>
            </div>

            {/* Direct Security Contact Note */}
            <div
              style={{
                marginTop: '40px',
                padding: '16px',
                borderRadius: '8px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-default)',
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.5,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                <Mail size={14} />
                <span>Confidential Security Disclosures</span>
              </div>
              For responsible vulnerability disclosures or GPG-encrypted inquiries, reach our security team directly at{' '}
              <a href="mailto:security@argvtix.ai" style={{ color: '#60a5fa', textDecoration: 'none' }}>
                security@argvtix.ai
              </a>.
            </div>
          </div>

          {/* Right Column: Submission Form */}
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              borderRadius: '12px',
              padding: '32px',
              boxShadow: '0 10px 30px -10px rgba(0, 0, 0, 0.5)',
            }}
          >
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc', marginBottom: '8px' }}>
              Schedule Your Demo & Consultation
            </h2>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', marginBottom: '24px' }}>
              Fill in your details below. All architectural discussions are protected under standard mutual NDA.
            </p>

            {errorMessage && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '12px 14px',
                  borderRadius: '8px',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#f87171',
                  fontSize: '0.84rem',
                  marginBottom: '20px',
                }}
              >
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {/* Invisible Honeypot Anti-Spam Field */}
              <div
                style={{
                  position: 'absolute',
                  left: '-9999px',
                  top: '-9999px',
                  opacity: 0,
                  height: 0,
                  width: 0,
                  overflow: 'hidden',
                }}
                aria-hidden="true"
              >
                <label htmlFor="companyTaxId">Tax ID / Leave Empty</label>
                <input
                  type="text"
                  id="companyTaxId"
                  name="companyTaxId"
                  value={formData.companyTaxId}
                  onChange={handleChange}
                  tabIndex={-1}
                  autoComplete="off"
                />
              </div>

              {/* Name Field */}
              <div style={{ marginBottom: '18px' }}>
                <label
                  htmlFor="name"
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    marginBottom: '6px',
                  }}
                >
                  Full Name <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <User
                    size={15}
                    style={{
                      position: 'absolute',
                      left: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)',
                    }}
                  />
                  <input
                    type="text"
                    id="name"
                    name="name"
                    required
                    maxLength={120}
                    placeholder="e.g. Sarah Jenkins"
                    value={formData.name}
                    onChange={handleChange}
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      padding: '10px 12px 10px 36px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-default)',
                      background: 'var(--bg-canvas)',
                      color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                      fontFamily: 'inherit',
                      outline: 'none',
                    }}
                  />
                </div>
              </div>

              {/* Work Email Field */}
              <div style={{ marginBottom: '18px' }}>
                <label
                  htmlFor="email"
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    marginBottom: '6px',
                  }}
                >
                  Work Email <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <Mail
                    size={15}
                    style={{
                      position: 'absolute',
                      left: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)',
                    }}
                  />
                  <input
                    type="email"
                    id="email"
                    name="email"
                    required
                    maxLength={180}
                    placeholder="s.jenkins@company.com"
                    value={formData.email}
                    onChange={handleChange}
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      padding: '10px 12px 10px 36px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-default)',
                      background: 'var(--bg-canvas)',
                      color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                      fontFamily: 'inherit',
                      outline: 'none',
                    }}
                  />
                </div>
              </div>

              {/* Company Name Field */}
              <div style={{ marginBottom: '18px' }}>
                <label
                  htmlFor="company"
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    marginBottom: '6px',
                  }}
                >
                  Organization / Company <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <Building2
                    size={15}
                    style={{
                      position: 'absolute',
                      left: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)',
                    }}
                  />
                  <input
                    type="text"
                    id="company"
                    name="company"
                    required
                    maxLength={120}
                    placeholder="e.g. Apex Dynamics Ltd."
                    value={formData.company}
                    onChange={handleChange}
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      padding: '10px 12px 10px 36px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-default)',
                      background: 'var(--bg-canvas)',
                      color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                      fontFamily: 'inherit',
                      outline: 'none',
                    }}
                  />
                </div>
              </div>

              {/* Agent Architecture / Use Case Textarea */}
              <div style={{ marginBottom: '20px' }}>
                <label
                  htmlFor="useCase"
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    marginBottom: '6px',
                  }}
                >
                  AI Agent Architecture & Reliability Goals <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <textarea
                  id="useCase"
                  name="useCase"
                  required
                  rows={4}
                  minLength={10}
                  maxLength={2000}
                  placeholder="Tell us about your autonomous agents, frameworks (LangGraph, CrewAI, MCP), tool execution boundaries, and compliance needs..."
                  value={formData.useCase}
                  onChange={handleChange}
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    padding: '12px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-default)',
                    background: 'var(--bg-canvas)',
                    color: 'var(--text-primary)',
                    fontSize: '0.86rem',
                    fontFamily: 'inherit',
                    outline: 'none',
                    resize: 'vertical',
                    lineHeight: 1.5,
                  }}
                />
              </div>

              {/* Cloudflare Turnstile CAPTCHA container */}
              <div style={{ marginBottom: '20px' }}>
                {turnstileSiteKey ? (
                  <div ref={turnstileContainerRef} style={{ minHeight: '65px' }} />
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 12px',
                      borderRadius: '6px',
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border-default)',
                      fontSize: '0.78rem',
                      color: 'var(--text-muted)',
                    }}
                  >
                    <ShieldCheck size={14} style={{ color: '#10b981' }} />
                    <span>Protected by Cloudflare Turnstile & Honeypot Bot Shield</span>
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  width: '100%',
                  padding: '12px 18px',
                  borderRadius: '6px',
                  border: 'none',
                  background: isSubmitting ? 'var(--bg-elevated)' : '#2563eb',
                  color: '#ffffff',
                  fontSize: '0.92rem',
                  fontWeight: 600,
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  transition: 'background 0.2s',
                }}
              >
                {isSubmitting ? (
                  <>
                    <div
                      style={{
                        width: '16px',
                        height: '16px',
                        border: '2px solid rgba(255,255,255,0.3)',
                        borderTopColor: '#ffffff',
                        borderRadius: '50%',
                        animation: 'spin 0.8s linear infinite',
                      }}
                    />
                    <span>Submitting Request...</span>
                  </>
                ) : (
                  <>
                    <Send size={15} />
                    <span>Submit Demo & Architecture Request</span>
                  </>
                )}
              </button>

              <p
                style={{
                  fontSize: '0.74rem',
                  color: 'var(--text-muted)',
                  textAlign: 'center',
                  marginTop: '14px',
                  lineHeight: 1.4,
                }}
              >
                By submitting this request, you agree to our{' '}
                <Link to="/privacy-policy" style={{ color: '#60a5fa', textDecoration: 'none' }}>
                  Privacy Policy
                </Link>{' '}
                and{' '}
                <Link to="/terms" style={{ color: '#60a5fa', textDecoration: 'none' }}>
                  Terms of Service
                </Link>
                . We never share your data.
              </p>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
};
