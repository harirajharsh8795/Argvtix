import React, { useState, useEffect } from 'react';
import { ShieldCheck, Settings, X, Check } from 'lucide-react';
import { getCookiePreferences, setCookiePreferences } from '../utils/cookieConsent';

export const CookieConsent: React.FC = () => {
  const [isVisible, setIsVisible] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [analyticsEnabled, setAnalyticsEnabled] = useState<boolean>(() => {
    return getCookiePreferences()?.analytics ?? false;
  });

  useEffect(() => {
    const prefs = getCookiePreferences();
    if (!prefs) {
      // Show banner after brief delay
      const timer = setTimeout(() => setIsVisible(true), 1000);
      return () => clearTimeout(timer);
    } else {
      setAnalyticsEnabled(prefs.analytics);
    }
  }, []);

  // Listen for global custom event to reopen preferences modal
  useEffect(() => {
    const handleOpen = () => {
      const prefs = getCookiePreferences();
      setAnalyticsEnabled(prefs ? prefs.analytics : false);
      setIsModalOpen(true);
    };

    window.addEventListener('proofline-open-cookie-settings', handleOpen);
    return () => window.removeEventListener('proofline-open-cookie-settings', handleOpen);
  }, []);

  const savePreferences = (analytics: boolean) => {
    setCookiePreferences(analytics);
    setAnalyticsEnabled(analytics);
    setIsVisible(false);
    setIsModalOpen(false);
  };

  const handleAcceptAll = () => savePreferences(true);
  const handleRejectAll = () => savePreferences(false);
  const handleSaveCustom = () => savePreferences(analyticsEnabled);

  return (
    <>
      {/* 1. BOTTOM BANNER */}
      {isVisible && !isModalOpen && (
        <aside
          role="region"
          aria-label="Privacy and Cookie Notice"
          style={{
            position: 'fixed',
            bottom: '20px',
            left: '20px',
            right: '20px',
            maxWidth: '680px',
            margin: '0 auto',
            background: 'rgba(13, 17, 26, 0.98)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '8px',
            padding: '18px 22px',
            boxShadow: '0 12px 36px rgba(0, 0, 0, 0.55)',
            backdropFilter: 'blur(12px)',
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
            fontFamily: 'var(--font-sans)',
            color: '#f8fafc',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10b981',
                flexShrink: 0,
              }}
            >
              <ShieldCheck size={18} />
            </div>

            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
                Privacy & Data Storage Notice
              </div>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5 }}>
                Proofline uses strictly necessary local storage to maintain session security and invariant guard states.
                We do not use advertising cookies. You can optionally allow privacy-first telemetry to help improve system reliability.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setIsModalOpen(true)}
              className="btn-action-secondary"
              style={{ padding: '6px 14px', fontSize: '0.78rem' }}
              aria-label="Customize Cookie Preferences"
            >
              <Settings size={13} />
              <span>Preferences</span>
            </button>

            <button
              onClick={handleRejectAll}
              className="btn-action-secondary"
              style={{ padding: '6px 14px', fontSize: '0.78rem' }}
            >
              Reject Non-Essential
            </button>

            <button
              onClick={handleAcceptAll}
              className="btn-action-primary"
              style={{ padding: '6px 16px', fontSize: '0.78rem' }}
            >
              Accept All
            </button>
          </div>
        </aside>
      )}

      {/* 2. CUSTOM PREFERENCES MODAL */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="cookie-modal-title"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(4, 6, 10, 0.78)',
            backdropFilter: 'blur(8px)',
            zIndex: 10000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
            fontFamily: 'var(--font-sans)',
          }}
          onClick={() => setIsModalOpen(false)}
        >
          <div
            style={{
              background: '#0d111a',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: '8px',
              maxWidth: '540px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 20px 48px rgba(0, 0, 0, 0.65)',
              color: '#f8fafc',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <ShieldCheck size={20} color="#10b981" />
                <h2 id="cookie-modal-title" style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                  Privacy & Cookie Preferences
                </h2>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                }}
                aria-label="Close dialog"
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5, marginBottom: '20px' }}>
              Configure how Proofline stores data in your browser. Changes are saved locally and can be modified at any time.
            </p>

            {/* Category 1: Essential (Required) */}
            <div
              style={{
                padding: '14px 16px',
                background: '#131824',
                border: '1px solid #1e2638',
                borderRadius: '6px',
                marginBottom: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.84rem', color: '#f8fafc' }}>Strictly Necessary</span>
                  <span style={{ fontSize: '0.68rem', padding: '2px 6px', borderRadius: '3px', background: '#1e293b', color: '#94a3b8', fontWeight: 600 }}>
                    REQUIRED
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981', fontSize: '0.78rem', fontWeight: 600 }}>
                  <Check size={14} />
                  <span>Always Active</span>
                </div>
              </div>
              <p style={{ margin: 0, fontSize: '0.76rem', color: '#64748b', lineHeight: 1.45 }}>
                Required to maintain JWT security tokens, verify user login state, and prevent CSRF attacks. Cannot be disabled.
              </p>
            </div>

            {/* Category 2: Analytics & Performance (Optional) */}
            <div
              style={{
                padding: '14px 16px',
                background: '#131824',
                border: '1px solid #1e2638',
                borderRadius: '6px',
                marginBottom: '24px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontWeight: 600, fontSize: '0.84rem', color: '#f8fafc' }}>
                  Privacy-Preserving Telemetry
                </span>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={analyticsEnabled}
                    onChange={(e) => setAnalyticsEnabled(e.target.checked)}
                    style={{ cursor: 'pointer', width: '16px', height: '16px', accentColor: '#10b981' }}
                    aria-label="Enable privacy-preserving telemetry"
                  />
                </label>
              </div>
              <p style={{ margin: 0, fontSize: '0.76rem', color: '#64748b', lineHeight: 1.45 }}>
                Collects aggregated, anonymous interaction metrics (e.g. simulation execution speed, error rates). Contains zero PII or model prompt contents.
              </p>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setIsModalOpen(false)}
                className="btn-action-secondary"
                style={{ padding: '8px 16px', fontSize: '0.82rem' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveCustom}
                className="btn-action-primary"
                style={{ padding: '8px 20px', fontSize: '0.82rem' }}
              >
                Save Preferences
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
