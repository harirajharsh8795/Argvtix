export interface CookiePreferences {
  essential: boolean;
  analytics: boolean;
  timestamp: string;
}

export const STORAGE_KEY = 'argvtix_cookie_consent';

export const getCookiePreferences = (): CookiePreferences | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // ignore
  }
  return null;
};

export const setCookiePreferences = (analytics: boolean): CookiePreferences => {
  const prefs: CookiePreferences = {
    essential: true,
    analytics,
    timestamp: new Date().toISOString(),
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // ignore
  }
  return prefs;
};
