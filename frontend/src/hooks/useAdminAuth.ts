import { useCallback, useEffect, useRef, useState } from "react";
import { useAppShell } from "../context/AppShellContext";
import { isStudioRole } from "../lib/authTokens";
import { ADMIN_AUTH_ERROR_EVENT } from "../lib/adminApi";
import { authMe, loginDesigner, logoutDesigner } from "../lib/designerApi";

type Me = { authenticated?: boolean; role?: string; email?: string };

export const ADMIN_ROLE = "ADMIN";

const SESSION_ENDED = "Your session ended. Sign in again.";

/**
 * Last confirmed admin session for this page load, so coming back to /admin
 * from another tab of the app doesn't flash the boot splash. Re-verified on mount.
 */
let lastAdmin: { email: string | null } | null = null;

export function wrongRoleMessage(role: string): string {
  return `Signed in as ${role}. Sign in with an admin account.`;
}

/**
 * Session guard for /admin/*.
 * `authed` is true only for `me.authenticated && me.role === "ADMIN"`.
 */
export function useAdminAuth() {
  const { setDesignerAuthed, authBootstrapped, designerAuthed } = useAppShell();
  const resume = !!lastAdmin && designerAuthed;
  const [authed, setAuthed] = useState(resume);
  const [bootstrapping, setBootstrapping] = useState(!resume);
  const [role, setRole] = useState<string | null>(resume ? ADMIN_ROLE : null);
  const [email, setEmail] = useState<string | null>(resume ? (lastAdmin?.email ?? null) : null);
  /** Message for the login view (wrong role, session ended). */
  const [notice, setNotice] = useState<string | null>(null);
  const epoch = useRef(0);
  const authedRef = useRef(false);
  authedRef.current = authed;
  const roleRef = useRef<string | null>(null);
  roleRef.current = role;

  const apply = useCallback(
    (me: Me | null) => {
      const signedIn = !!me?.authenticated;
      const r = signedIn ? String(me?.role || "") : null;
      const ok = signedIn && r === ADMIN_ROLE;
      lastAdmin = ok ? { email: me?.email ?? null } : null;
      setRole(r);
      setEmail(signedIn ? (me?.email ?? null) : null);
      setAuthed(ok);
      // Keep the app header's logout button in sync (it shows for studio roles).
      setDesignerAuthed(signedIn && isStudioRole(r ?? undefined));
      setNotice(signedIn && !ok && r ? wrongRoleMessage(r) : null);
      return ok;
    },
    [setDesignerAuthed],
  );

  // Initial session check, once the app shell has done its own.
  useEffect(() => {
    if (!authBootstrapped) return;
    const id = ++epoch.current;
    void (authMe() as Promise<Me>)
      .then((me) => {
        if (id === epoch.current) apply(me);
      })
      .catch(() => {
        if (id === epoch.current) apply(null);
      })
      .finally(() => {
        if (id === epoch.current) setBootstrapping(false);
      });
  }, [apply, authBootstrapped]);

  // Header logout clears designerAuthed; drop back to a clean login view.
  useEffect(() => {
    if (authBootstrapped && !designerAuthed && isStudioRole(roleRef.current ?? undefined)) {
      epoch.current += 1;
      lastAdmin = null;
      setAuthed(false);
      setRole(null);
      setEmail(null);
      setNotice(null);
    }
  }, [authBootstrapped, designerAuthed]);

  // Any admin call that still fails with 401/403 ends the session view.
  useEffect(() => {
    const onAuthError = () => {
      if (!authedRef.current) return;
      epoch.current += 1;
      lastAdmin = null;
      setAuthed(false);
      setRole(null);
      roleRef.current = null;
      setNotice(SESSION_ENDED);
      void (authMe() as Promise<Me>)
        .then((me) => {
          if (!me?.authenticated) setDesignerAuthed(false);
        })
        .catch(() => setDesignerAuthed(false));
    };
    window.addEventListener(ADMIN_AUTH_ERROR_EVENT, onAuthError);
    return () => window.removeEventListener(ADMIN_AUTH_ERROR_EVENT, onAuthError);
  }, [setDesignerAuthed]);

  const signIn = useCallback(
    async (emailInput: string, password: string): Promise<boolean> => {
      const id = ++epoch.current;
      setNotice(null);
      const login = await loginDesigner(emailInput, password);
      if (id !== epoch.current) return false;
      // Confirm the role server-side; fall back to the login payload if /me is slow.
      let me: Me = { authenticated: true, role: login.role, email: login.email };
      try {
        const fromServer = (await authMe()) as Me;
        if (fromServer?.authenticated) me = fromServer;
      } catch {
        /* use login payload */
      }
      if (id !== epoch.current) return false;
      setBootstrapping(false);
      return apply(me);
    },
    [apply],
  );

  const signOut = useCallback(async () => {
    epoch.current += 1;
    try {
      await logoutDesigner();
    } finally {
      apply(null);
    }
  }, [apply]);

  return { authed, bootstrapping, role, email, notice, setNotice, signIn, signOut };
}
