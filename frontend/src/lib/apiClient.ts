import { clearAuthTokens, getAuthTokens, refreshAccessToken } from "./authTokens";

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function ensureCsrf(): Promise<string | null> {
  const existing = getCookie("csrftoken");
  if (existing) return existing;
  const res = await fetch("/api/auth/csrf/", { credentials: "include" });
  const fromCookie = getCookie("csrftoken");
  if (fromCookie) return fromCookie;
  try {
    const body = (await res.json()) as { csrfToken?: string };
    if (body.csrfToken) return body.csrfToken;
  } catch {
    /* ignore */
  }
  return null;
}

function attachAuthHeaders(headers: Headers) {
  const tokens = getAuthTokens();
  if (tokens?.access && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${tokens.access}`);
  }
}

async function buildRequestInit(init: RequestInit = {}): Promise<RequestInit> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  attachAuthHeaders(headers);
  if (method !== "GET" && method !== "HEAD") {
    const csrf = (await ensureCsrf()) || getCookie("csrftoken");
    if (csrf) headers.set("X-CSRFToken", csrf);
  }
  if (
    !headers.has("Content-Type") &&
    init.body &&
    !(init.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }
  return { ...init, headers, credentials: "include" };
}

function shouldAttemptRefresh(path: string, retried: boolean): boolean {
  if (retried) return false;
  if (path.includes("/auth/login")) return false;
  if (path.includes("/auth/token/refresh")) return false;
  return true;
}

/** Shared fetch: Bearer JWT, CSRF for session-backed POSTs, automatic refresh on 401. */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
  retried = false,
): Promise<Response> {
  const built = await buildRequestInit(init);
  const res = await fetch(path, built);
  if (res.status === 401 && shouldAttemptRefresh(path, retried)) {
    const access = await refreshAccessToken();
    if (access) return apiFetch(path, init, true);
    clearAuthTokens();
  }
  return res;
}
