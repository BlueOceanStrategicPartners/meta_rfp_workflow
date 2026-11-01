import { useCallback, useEffect, useRef, useState } from "react";
import { authMe, type LoginSessionPayload } from "../lib/designerApi";
import { useAppShell } from "../context/AppShellContext";

export type StudioPortalMode = "designer" | "map";

function isAuthedForMode(
  me: { authenticated?: boolean; role?: string },
  mode: StudioPortalMode,
): boolean {
  if (!me.authenticated) return false;
  if (mode === "designer") return me.role === "DESIGNER";
  return me.role === "DESIGNER" || me.role === "ADMIN";
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Session bootstrap for Designer / Map Studio portals. */
export function useStudioPortalAuth(mode: StudioPortalMode) {
  const { designerAuthed, setDesignerAuthed, authBootstrapped } = useAppShell();
  const [authed, setAuthed] = useState(designerAuthed);
  const [bootstrapping, setBootstrapping] = useState(!authBootstrapped);
  const sessionEpoch = useRef(0);

  const applySession = useCallback(
    (me: { authenticated?: boolean; role?: string }) => {
      const ok = isAuthedForMode(me, mode);
      setAuthed(ok);
      setDesignerAuthed(ok);
      return ok;
    },
    [mode, setDesignerAuthed],
  );

  useEffect(() => {
    if (!authBootstrapped) return;
    const epoch = ++sessionEpoch.current;
    void authMe()
      .then((me) => {
        if (epoch !== sessionEpoch.current) return;
        applySession(me);
      })
      .catch(() => {
        if (epoch !== sessionEpoch.current) return;
        setAuthed(false);
        setDesignerAuthed(false);
      })
      .finally(() => {
        if (epoch === sessionEpoch.current) setBootstrapping(false);
      });
  }, [applySession, authBootstrapped, mode, setDesignerAuthed]);

  useEffect(() => {
    if (authBootstrapped && designerAuthed && !authed) {
      setAuthed(true);
      setBootstrapping(false);
    }
  }, [authBootstrapped, authed, designerAuthed]);

  useEffect(() => {
    if (authBootstrapped && !designerAuthed) {
      setAuthed(false);
    }
  }, [authBootstrapped, designerAuthed]);

  /**
   * After POST /api/auth/login/ succeeds. Uses login JSON immediately, then
   * verifies /api/auth/me/ (with retries) so a slow Set-Cookie does not block entry.
   */
  const confirmSession = useCallback(
    async (fromLogin?: LoginSessionPayload): Promise<boolean> => {
      sessionEpoch.current += 1;
      const epoch = sessionEpoch.current;

      const loginOk =
        !!fromLogin?.role &&
        isAuthedForMode({ authenticated: true, role: fromLogin.role }, mode);

      if (loginOk) {
        applySession({ authenticated: true, role: fromLogin!.role });
        setBootstrapping(false);
      }

      for (let attempt = 0; attempt < 4; attempt += 1) {
        if (attempt > 0) await sleep(60 * attempt);
        try {
          const me = await authMe();
          if (epoch !== sessionEpoch.current) return loginOk;
          if (isAuthedForMode(me, mode)) {
            applySession(me);
            setBootstrapping(false);
            return true;
          }
        } catch {
          /* retry */
        }
      }

      if (loginOk) return true;

      setAuthed(false);
      setDesignerAuthed(false);
      setBootstrapping(false);
      return false;
    },
    [applySession, mode, setDesignerAuthed],
  );

  return { authed, bootstrapping, confirmSession, setAuthed, setDesignerAuthed };
}
