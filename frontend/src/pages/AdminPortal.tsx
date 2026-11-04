import { Navigate, Route, Routes } from "react-router-dom";
import AdminLayout, { AdminShell } from "../components/admin/AdminLayout";
import StudioPortalBootSplash from "../components/designer/StudioPortalBootSplash";
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

/** /admin/* — sign-in guard, then the admin layout with nested module routes. */
export default function AdminPortal() {
  const { authed, bootstrapping, email } = useAdminAuth();

  if (bootstrapping) {
    return (
      <AdminShell className="items-center justify-center">
        <StudioPortalBootSplash title={TITLE} />
      </AdminShell>
    );
  }

  if (!authed) {
    return <Navigate to="/login" replace />;
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
