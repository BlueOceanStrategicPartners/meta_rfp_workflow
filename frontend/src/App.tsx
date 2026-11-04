import { useState } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import ConfirmDialog from "./components/designer/ConfirmDialog";
import TemplateIconButton, { IconLogout, IconMoon, IconSun } from "./components/designer/TemplateIconButton";
import { IconNavSubtitles } from "./components/AppNavIcons";
import { useAppShell } from "./context/AppShellContext";
import { logoutDesigner } from "./lib/designerApi";
import ClientWorkspace from "./pages/ClientWorkspace";
import DesignerPortal from "./pages/DesignerPortal";
import AdminPortal from "./pages/AdminPortal";
import UnifiedLoginPage from "./pages/UnifiedLoginPage";

export default function App() {
  const {
    theme,
    toggleTheme,
    designerAuthed,
    setDesignerAuthed,
    clientAuthed,
    setClientAuthed,
    clientSubtitlesEnabled,
    toggleClientSubtitles,
    clientProposalFullscreen,
  } = useAppShell();
  const location = useLocation();
  const navigate = useNavigate();

  const onClient = location.pathname === "/client" || location.pathname.startsWith("/client/");
  const onStudio = location.pathname.startsWith("/designer");
  const onAdmin = location.pathname.startsWith("/admin");
  const showLogout = clientAuthed || designerAuthed;

  const [confirmLogoutOpen, setConfirmLogoutOpen] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);

  const handleLogout = async () => {
    setLogoutBusy(true);
    try {
      await logoutDesigner();
      setClientAuthed(false);
      setDesignerAuthed(false);
    } finally {
      setConfirmLogoutOpen(false);
      setLogoutBusy(false);
      navigate("/login", { replace: true });
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
      <header className={`app-shell-header ${clientProposalFullscreen ? "hidden" : ""}`} role="banner">
        <div className="app-shell-header__brand">
          <span className="app-shell-header__brand-title">RFP Engine</span>
        </div>
        <div className="app-shell-header__actions studio-toolbar">
          {onClient && clientAuthed && (
            <TemplateIconButton
              compact
              label={clientSubtitlesEnabled ? "Hide subtitles" : "Show subtitles"}
              selected={clientSubtitlesEnabled}
              onClick={toggleClientSubtitles}
            >
              <IconNavSubtitles off={!clientSubtitlesEnabled} />
            </TemplateIconButton>
          )}
          <TemplateIconButton
            compact
            label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            selected={theme === "light"}
            onClick={toggleTheme}
          >
            {theme === "dark" ? <IconSun /> : <IconMoon />}
          </TemplateIconButton>
          {showLogout && (onClient || onStudio || onAdmin) && (
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
          <Route path="/" element={<UnifiedLoginPage />} />
          <Route path="/login" element={<UnifiedLoginPage />} />
          <Route path="/client" element={<ClientWorkspace />} />
          <Route path="/designer" element={<DesignerPortal />} />
          <Route path="/admin/*" element={<AdminPortal />} />
        </Routes>
      </main>
    </div>
  );
}
