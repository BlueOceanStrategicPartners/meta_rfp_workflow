import { authMe, type LoginSessionPayload } from "./designerApi";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export type AuthMePayload = {
  authenticated?: boolean;
  role?: string;
  email?: string;
};

/** Verify session cookie/JWT after login (retries for slow Set-Cookie). */
export async function confirmAuthSession(fromLogin?: LoginSessionPayload): Promise<AuthMePayload | null> {
  const loginRole = fromLogin?.role;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (attempt > 0) await sleep(60 * attempt);
    try {
      const me = (await authMe()) as AuthMePayload;
      if (me.authenticated && me.role) return me;
    } catch {
      /* retry */
    }
  }
  if (loginRole) {
    return { authenticated: true, role: loginRole, email: fromLogin?.email };
  }
  return null;
}
