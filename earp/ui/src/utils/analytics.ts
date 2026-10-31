import { getCookiePreferences } from './cookieConsent';

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

const GA_ID = import.meta.env.VITE_GA_MEASUREMENT_ID || '';
let isInitialized = false;

/**
 * Initializes Google Analytics 4 strictly after obtaining explicit user consent.
 * IP anonymization is enforced by default.
 */
export function initGA4(): boolean {
  if (typeof window === 'undefined') return false;
  if (isInitialized) return true;

  const prefs = getCookiePreferences();
  if (!prefs || !prefs.analytics) {
    // User has not consented to analytics tracking
    return false;
  }

  if (!GA_ID) {
    // In development or when measurement ID is unset, log gracefully without errors
    if (import.meta.env.DEV) {
      console.info('[Analytics] GA4 skipped: VITE_GA_MEASUREMENT_ID is not configured.');
    }
    return false;
  }

  try {
    // Inject gtag.js script
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA_ID)}`;
    document.head.appendChild(script);

    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
      // eslint-disable-next-line prefer-rest-params
      window.dataLayer?.push(arguments);
    };

    window.gtag('js', new Date());
    window.gtag('config', GA_ID, {
      anonymize_ip: true,
      send_page_view: false, // We handle SPA page views manually
    });

    isInitialized = true;
    return true;
  } catch (err) {
    console.error('[Analytics] Failed to initialize GA4:', err);
    return false;
  }
}

/**
 * Tracks SPA route changes when analytics consent is present.
 */
export function trackPageView(path: string, title?: string): void {
  if (typeof window === 'undefined') return;

  const prefs = getCookiePreferences();
  if (!prefs?.analytics) return;

  if (!isInitialized) {
    const initialized = initGA4();
    if (!initialized) return;
  }

  if (window.gtag && GA_ID) {
    window.gtag('event', 'page_view', {
      page_path: path,
      page_title: title || document.title,
    });
  }
}

/**
 * Tracks custom product and lead events (e.g. form submission, demo request).
 */
export function trackEvent(eventName: string, params: Record<string, unknown> = {}): void {
  if (typeof window === 'undefined') return;

  const prefs = getCookiePreferences();
  if (!prefs?.analytics) return;

  if (!isInitialized) {
    const initialized = initGA4();
    if (!initialized) return;
  }

  if (window.gtag) {
    window.gtag('event', eventName, params);
  }
}

// Automatically bind listener for runtime consent updates
if (typeof window !== 'undefined') {
  window.addEventListener('cookie_consent_updated', () => {
    const prefs = getCookiePreferences();
    if (prefs?.analytics && !isInitialized) {
      initGA4();
    }
  });
}
