import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./app/AppShell";
import { AuthProvider, useAuth } from "./app/AuthProvider";
import { Alerts } from "./pages/Alerts";
import { Catalog } from "./pages/Catalog";
import { Home } from "./pages/Home";
import { IncidentDetail } from "./pages/IncidentDetail";
import { Incidents } from "./pages/Incidents";
import { InsightsPage } from "./pages/InsightsPage";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { OnCall } from "./pages/OnCall";
import { PostIncident } from "./pages/PostIncident";
import { PublicStatus } from "./pages/PublicStatus";
import { StatusPageView } from "./pages/StatusPageView";
import { Workflows } from "./pages/Workflows";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="authShell">Loading…</div>;
  if (!session) {
    // The root is the marketing site when signed out; anything deeper asks to sign in.
    if (location.pathname === "/") return <Landing />;
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

function LoginRoute() {
  const { session, loading } = useAuth();
  if (loading) return <div className="authShell">Loading…</div>;
  if (session) return <Navigate to="/" replace />;
  return <Login />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          {/* The customer-facing status page needs no account, like a real one. */}
          <Route path="/status" element={<PublicStatus />} />

          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<Home />} />
            <Route path="incidents" element={<Incidents />} />
            <Route path="incidents/:reference" element={<IncidentDetail />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="on-call" element={<OnCall />} />
            <Route path="status-page" element={<StatusPageView />} />
            <Route path="post-incident" element={<PostIncident />} />
            <Route path="insights" element={<InsightsPage />} />
            <Route path="catalog" element={<Catalog />} />
            <Route path="workflows" element={<Workflows />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
