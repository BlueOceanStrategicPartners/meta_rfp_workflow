const ACCESS_KEY = "rfp_auth_access";
const REFRESH_KEY = "rfp_auth_refresh";

export type AuthTokens = {
  access: string;
  refresh: string;
};

export function getAuthTokens(): AuthTokens | null {
  try {
    const access = localStorage.getItem(ACCESS_KEY);
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (!access || !refresh) return null;
    return { access, refresh };
  } catch {
    return null;
  }
}

export function setAuthTokens(access: string, refresh: string) {
  try {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  } catch {
    /* ignore */
  }
}

export function clearAuthTokens() {
  try {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* ignore */
  }
}

let refreshInFlight: Promise<string | null> | null = null;

async function doRefreshAccessToken(): Promise<string | null> {
  const stored = getAuthTokens();
  if (!stored?.refresh) return null;
  try {
    const res = await fetch("/api/auth/token/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ refresh: stored.refresh }),
    });
    if (!res.ok) {
      clearAuthTokens();
      return null;
    }
    const body = (await res.json()) as { access?: string; refresh?: string };
    if (!body.access) {
      clearAuthTokens();
      return null;
    }
    setAuthTokens(body.access, body.refresh ?? stored.refresh);
    return body.access;
  } catch {
    clearAuthTokens();
    return null;
  }
}

/** Exchange refresh token for a new access token (and rotated refresh when enabled). */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = doRefreshAccessToken();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

export function getAuthorizationHeader(): string | null {
  const tokens = getAuthTokens();
  return tokens?.access ? `Bearer ${tokens.access}` : null;
}

export function isStudioRole(role?: string): boolean {
  return role === "DESIGNER" || role === "ADMIN";
}
