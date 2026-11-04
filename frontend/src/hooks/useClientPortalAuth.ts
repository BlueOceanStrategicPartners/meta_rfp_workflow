import { useCallback, useEffect, useRef, useState } from "react";
import { authMe, type LoginSessionPayload } from "../lib/clientApi";
import { useAppShell } from "../context/AppShellContext";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useClientPortalAuth() {
  const { clientAuthed, setClientAuthed, authBootstrapped } = useAppShell();
  const [authed, setAuthed] = useState(clientAuthed);
  const [bootstrapping, setBootstrapping] = useState(!authBootstrapped);
  const sessionEpoch = useRef(0);

  const applySession = useCallback(
    (me: { authenticated?: boolean; role?: string }) => {
      const ok = !!me.authenticated && me.role === "CLIENT";
      setAuthed(ok);
      setClientAuthed(ok);
      return ok;
    },
    [setClientAuthed],
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
        setClientAuthed(false);
      })
      .finally(() => {
        if (epoch === sessionEpoch.current) setBootstrapping(false);
      });
  }, [applySession, authBootstrapped, setClientAuthed]);

  useEffect(() => {
    if (authBootstrapped && clientAuthed && !authed) {
      setAuthed(true);
      setBootstrapping(false);
    }
  }, [authBootstrapped, authed, clientAuthed]);

  useEffect(() => {
    if (authBootstrapped && !clientAuthed) setAuthed(false);
  }, [authBootstrapped, clientAuthed]);

  const confirmSession = useCallback(
    async (fromLogin?: LoginSessionPayload): Promise<boolean> => {
      sessionEpoch.current += 1;
      const epoch = sessionEpoch.current;
      const loginOk = fromLogin?.role === "CLIENT";

      if (loginOk) {
        applySession({ authenticated: true, role: "CLIENT" });
        setBootstrapping(false);
      }

      for (let attempt = 0; attempt < 4; attempt += 1) {
        if (attempt > 0) await sleep(60 * attempt);
        try {
          const me = await authMe();
          if (epoch !== sessionEpoch.current) return loginOk;
          if (me.authenticated && me.role === "CLIENT") {
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
      setClientAuthed(false);
      setBootstrapping(false);
      return false;
    },
    [applySession, setClientAuthed],
  );

  return { authed, bootstrapping, confirmSession };
}
