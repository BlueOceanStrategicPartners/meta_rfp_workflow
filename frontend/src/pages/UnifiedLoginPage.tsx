import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import StudioPortalLogin from "../components/designer/StudioPortalLogin";
import { useAppShell } from "../context/AppShellContext";
import { confirmAuthSession } from "../lib/confirmAuthSession";
import { authMe, loginDesigner } from "../lib/designerApi";
import { homePathForRole } from "../lib/portalRoutes";
import { syncAppShellFromRole } from "../lib/syncAppShellAuth";

const DEMO_CLIENT = { email: "client@demo.local", password: "demo12345" };
const DEMO_DESIGNER = { email: "designer@demo.local", password: "demo12345" };

export default function UnifiedLoginPage() {
  const navigate = useNavigate();
  const { authBootstrapped, setClientAuthed, setDesignerAuthed } = useAppShell();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resolvedRole, setResolvedRole] = useState<string | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);

  useEffect(() => {
    if (!authBootstrapped) return;
    let cancelled = false;
    void (async () => {
      try {
        const me = (await authMe()) as { authenticated?: boolean; role?: string };
        if (cancelled) return;
        if (me.authenticated && me.role) {
          syncAppShellFromRole(me.role, setClientAuthed, setDesignerAuthed);
          setResolvedRole(me.role);
        }
      } catch {
        /* stay on login */
      } finally {
        if (!cancelled) setSessionChecked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authBootstrapped, setClientAuthed, setDesignerAuthed]);

  if (!authBootstrapped || !sessionChecked) {
    return (
      <div className="flex h-full min-h-[50vh] items-center justify-center text-sm client-hint-muted">
        Loading…
      </div>
    );
  }

  if (resolvedRole) {
    return <Navigate to={homePathForRole(resolvedRole)} replace />;
  }

  const runLogin = async (loginEmail: string, loginPassword: string) => {
    if (busy) return;
    if (!loginEmail.trim() || !loginPassword) {
      setError("Enter your email and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const session = await loginDesigner(loginEmail, loginPassword);
      const me = await confirmAuthSession(session);
      const role = me?.role ?? session.role;
      if (!role) {
        setError("Signed in but session was not saved. Allow cookies for this site and try again.");
        return;
      }
      syncAppShellFromRole(role, setClientAuthed, setDesignerAuthed);
      navigate(homePathForRole(role), { replace: true });
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Sign-in failed. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <StudioPortalLogin
      title="Sign in"
      subtitle="Use your email and password — we'll open the right portal for your account."
      error={error}
      email={email}
      password={password}
      busy={busy}
      onEmailChange={setEmail}
      onPasswordChange={setPassword}
      onSubmit={() => runLogin(email, password)}
      onMockSso={async (provider) => {
        const demo = provider === "microsoft" ? DEMO_CLIENT : DEMO_DESIGNER;
        setEmail(demo.email);
        setPassword(demo.password);
        await runLogin(demo.email, demo.password);
      }}
    />
  );
}
