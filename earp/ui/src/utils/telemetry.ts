/**
 * Privacy-First Telemetry Dispatcher for Proofline
 * Strictly enforces user consent preferences before recording or emitting any metric.
 * Never collects or transmits PII, passwords, prompts, or authorization tokens.
 */

import { getCookiePreferences } from './cookieConsent';

export interface TelemetryEvent {
  category: 'interaction' | 'simulator' | 'navigation' | 'error';
  action: string;
  label?: string;
  value?: number;
}

export const trackEvent = (event: TelemetryEvent): void => {
  const prefs = getCookiePreferences();
  
  // Strict Privacy Gate: Do not record if user has not explicitly consented to analytics
  if (!prefs || !prefs.analytics) {
    return;
  }

  const payload = {
    ...event,
    timestamp: new Date().toISOString(),
    anonymized_session: 'anon_' + Math.random().toString(36).substring(2, 10),
  };

  // In development, log locally if permitted
  if (import.meta.env.DEV) {
    console.debug('[Telemetry Allowed]', payload);
  }
};
