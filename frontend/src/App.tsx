import { useState } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import ConfirmDialog from "./components/designer/ConfirmDialog";
import TemplateIconButton, { IconLogout, IconMoon, IconSun } from "./components/designer/TemplateIconButton";
import {
  IconNavAdmin,
  IconNavClient,
  IconNavDesigner,
  IconNavMap,
} from "./components/AppNavIcons";
import { useAppShell } from "./context/AppShellContext";
import { logoutDesigner } from "./lib/designerApi";
import ClientWorkspace from "./pages/ClientWorkspace";
import DesignerPortal from "./pages/DesignerPortal";
import MapStudioPortal from "./pages/MapStudioPortal";
import AdminPortal from "./pages/AdminPortal";

const PRIMARY_NAV = [
  { to: "/client", label: "Client", Icon: IconNavClient },
  { to: "/designer", label: "Designer", Icon: IconNavDesigner },
  { to: "/map", label: "Map Studio", Icon: IconNavMap },
  { to: "/admin", label: "Admin", Icon: IconNavAdmin },
] as const;

export default function App() {
  const { theme, toggleTheme, designerAuthed, setDesignerAuthed } = useAppShell();
  const location = useLocation();
  const navigate = useNavigate();

  const navLinkClass =
    (to: string) =>
    ({ isActive }: { isActive: boolean }) => {
      const active =
        to === "/client" ? isActive || location.pathname === "/" : isActive;
      return ["app-nav-link", active ? "app-nav-link-active" : "app-nav-link-inactive"].join(" ");
    };
  const onStudio =
    location.pathname.startsWith("/designer") || location.pathname.startsWith("/map");

  const studioLoginPath = location.pathname.startsWith("/map") ? "/map" : "/designer";
  const [confirmLogoutOpen, setConfirmLogoutOpen] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);

  const handleLogout = async () => {
    setLogoutBusy(true);
    try {
      await logoutDesigner();
    } finally {
      setDesignerAuthed(false);
      setConfirmLogoutOpen(false);
      setLogoutBusy(false);
      navigate(studioLoginPath, { replace: true });
    }
  };

  return (
    <div className="app-shell-canvas">
      <ConfirmDialog
        open={confirmLogoutOpen}
        title="Log out?"
        message="Are you sure you want to log out?"
        confirmLabel={logoutBusy ? "Logging out…" : "Log out"}
        cancelLabel="Cancel"
        confirmVariant="danger"
        confirmDisabled={logoutBusy}
        onCancel={() => {
          if (!logoutBusy) setConfirmLogoutOpen(false);
        }}
        onConfirm={() => {
          if (!logoutBusy) void handleLogout();
        }}
      />
      <header className="app-shell-header" role="banner">
        <div className="app-shell-header__brand">
          <span className="hidden text-white/90 sm:inline">RFP Engine</span>
          <span className="hidden text-white/35 sm:inline">/</span>
          <nav className="app-nav-tabs" aria-label="Primary">
            {PRIMARY_NAV.map(({ to, label, Icon }) => (
              <NavLink key={to} to={to} className={navLinkClass(to)} end={to !== "/client"}>
                <Icon />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="app-shell-header__actions studio-toolbar">
          <TemplateIconButton
            compact
            label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            selected={theme === "light"}
            onClick={toggleTheme}
          >
            {theme === "dark" ? <IconSun /> : <IconMoon />}
          </TemplateIconButton>
          {onStudio && designerAuthed && (
            <TemplateIconButton
              compact
              label="Log out"
              variant="danger"
              onClick={() => setConfirmLogoutOpen(true)}
            >
              <IconLogout />
            </TemplateIconButton>
          )}
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<ClientWorkspace />} />
          <Route path="/client" element={<ClientWorkspace />} />
          <Route path="/designer" element={<DesignerPortal />} />
          <Route path="/map" element={<MapStudioPortal />} />
          <Route path="/admin" element={<AdminPortal />} />
        </Routes>
      </main>
    </div>
  );
}
