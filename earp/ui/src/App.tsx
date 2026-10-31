import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { LandingPage } from './pages/LandingPage';
import { ContactPage } from './pages/ContactPage';
import { ThankYouPage } from './pages/ThankYouPage';
import { PrivacyPage } from './pages/PrivacyPage';
import { TermsPage } from './pages/TermsPage';
import { OverviewPage } from './pages/OverviewPage';
import { TracesPage } from './pages/TracesPage';
import { GuardPage } from './pages/GuardPage';
import { EvalsPage } from './pages/EvalsPage';
import { WatchdogPage } from './pages/WatchdogPage';
import { SecurityPage } from './pages/SecurityPage';
import { BenchmarkPage } from './pages/BenchmarkPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { CookieConsent } from './components/CookieConsent';
import { api } from './api/client';
import { trackPageView } from './utils/analytics';

function AnalyticsTracker() {
  const location = useLocation();

  useEffect(() => {
    trackPageView(location.pathname);
  }, [location.pathname]);

  return null;
}

function DashboardLayout() {
  const location = useLocation();
  const [pendingApprovals, setPendingApprovals] = useState<number>(0);
  const [activeAnomalies, setActiveAnomalies] = useState<number>(0);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchBadgeCounts = async () => {
    setIsRefreshing(true);
    try {
      const [approvalsRes, anomalyRes] = await Promise.all([
        api.getApprovals('pending').catch(() => ({ total: 0 })),
        api.getAnomalyReport().catch(() => ({ anomalies_detected: 0 })),
      ]);
      setPendingApprovals(approvalsRes.total || 0);
      setActiveAnomalies(anomalyRes.anomalies_detected || 0);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchBadgeCounts();
    const interval = setInterval(fetchBadgeCounts, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-container">
      {/* Navigation Sidebar */}
      <Sidebar
        pendingApprovalsCount={pendingApprovals}
        anomalyCount={activeAnomalies}
      />

      {/* Main Content Area */}
      <div className="main-content">
        <TopBar onRefresh={fetchBadgeCounts} isRefreshing={isRefreshing} />

        <main className="page-wrapper" style={{ display: 'flex', flexDirection: 'column' }}>
          <div key={location.pathname} className="page-transition-enter" style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      {/* Privacy-gated SPA Route Analytics Tracker */}
      <AnalyticsTracker />

      <Routes>
        {/* Public Website Routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/demo" element={<Navigate to="/contact" replace />} />
        <Route path="/request-demo" element={<Navigate to="/contact" replace />} />
        <Route path="/thank-you" element={<ThankYouPage />} />
        <Route path="/privacy-policy" element={<PrivacyPage />} />
        <Route path="/privacy" element={<Navigate to="/privacy-policy" replace />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/terms-of-service" element={<Navigate to="/terms" replace />} />
        <Route path="/404" element={<NotFoundPage />} />

        {/* Console & Observability Routes */}
        <Route path="/console" element={<Navigate to="/overview" replace />} />
        <Route path="/app" element={<Navigate to="/overview" replace />} />
        <Route element={<DashboardLayout />}>
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/traces" element={<TracesPage />} />
          <Route path="/guard" element={<GuardPage />} />
          <Route path="/evals" element={<EvalsPage />} />
          <Route path="/watchdog" element={<WatchdogPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route path="/benchmark" element={<BenchmarkPage />} />
        </Route>

        {/* Branded 404 Catch-All */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>

      {/* Global Privacy & Cookie Consent Controller */}
      <CookieConsent />
    </BrowserRouter>
  );
}

export default App;
