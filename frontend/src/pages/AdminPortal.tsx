import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AdminLayout, { AdminShell } from "../components/admin/AdminLayout";
import StudioPortalBootSplash from "../components/designer/StudioPortalBootSplash";
import StudioPortalLogin from "../components/designer/StudioPortalLogin";
import { useAdminAuth } from "../hooks/useAdminAuth";
import DebateDetailPage from "./admin/DebateDetailPage";
import DebatesPage from "./admin/DebatesPage";
import InventoryPage from "./admin/InventoryPage";
import NegotiationsPage from "./admin/NegotiationsPage";
import OccupancyPage from "./admin/OccupancyPage";
import OverviewPage from "./admin/OverviewPage";
import PricingPage from "./admin/PricingPage";
import TelemetryPage from "./admin/TelemetryPage";

const TITLE = "Admin Command Center";
const DEMO_ADMIN_EMAIL = "admin@demo.local";
const DEMO_ADMIN_PASSWORD = "admin12345";

/** /admin/* — sign-in guard, then the admin layout with nested module routes. */
export default function AdminPortal() {
  const { authed, bootstrapping, email, notice, setNotice, signIn } = useAdminAuth();
  const [emailInput, setEmailInput] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  if (bootstrapping) {
    return (
      <AdminShell className="items-center justify-center">
        <StudioPortalBootSplash title={TITLE} />
      </AdminShell>
    );
  }

  if (!authed) {
    const runSignIn = async (loginEmail: string, loginPassword: string) => {
      if (busy) return;
      if (!loginEmail.trim() || !loginPassword) {
        setLoginError("Enter your email and password.");
        return;
      }
      setBusy(true);
      setLoginError(null);
      setNotice(null);
      try {
        const ok = await signIn(loginEmail, loginPassword);
        if (ok) setPassword("");
      } catch (err) {
        setLoginError(err instanceof Error && err.message ? err.message : "Sign-in failed. Please try again.");
      } finally {
        setBusy(false);
      }
    };

    return (
      <AdminShell scrollable>
        <StudioPortalLogin
          title={TITLE}
          subtitle="Sign in with your admin account"
          error={loginError ?? notice}
          email={emailInput}
          password={password}
          busy={busy}
          onEmailChange={setEmailInput}
          onPasswordChange={setPassword}
          onSubmit={() => runSignIn(emailInput, password)}
          onMockSso={async () => {
            // Same demo shortcut as the Designer portal: the Microsoft/Google buttons sign in the demo account.
            setEmailInput(DEMO_ADMIN_EMAIL);
            setPassword(DEMO_ADMIN_PASSWORD);
            await runSignIn(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD);
          }}
        />
      </AdminShell>
    );
  }

  return (
    <AdminLayout email={email}>
      <Routes>
        <Route index element={<OverviewPage />} />
        <Route path="debates" element={<DebatesPage />} />
        <Route path="debates/:rfpId" element={<DebateDetailPage />} />
        <Route path="pricing" element={<PricingPage />} />
        <Route path="negotiations" element={<NegotiationsPage />} />
        <Route path="inventory" element={<InventoryPage />} />
        <Route path="occupancy" element={<OccupancyPage />} />
        <Route path="telemetry" element={<TelemetryPage />} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AdminLayout>
  );
}
