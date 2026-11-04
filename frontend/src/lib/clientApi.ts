import { apiFetch } from "./apiClient";
import { setAuthTokens, type AuthTokens } from "./authTokens";
import { authMe, logoutDesigner, type LoginSessionPayload } from "./designerApi";

export type ClientRfpSessionSummary = {
  id: string;
  status: string;
  completed: boolean;
  title: string;
  updated_at: string;
  created_at: string;
  last_snippet: string;
  proposal_card?: {
    company_name?: string;
    check_in_date?: string;
    check_out_date?: string;
    peak_rooms?: number;
    headcount?: number;
    estimate?: string;
  } | null;
};

export type ClientRfpSessionDetail = {
  id: string;
  status: string;
  completed: boolean;
  active_ui_cards_json: Record<string, unknown>;
  client_session: Record<string, unknown>;
  source_document_text?: string;
};

export async function loginClient(email: string, password: string): Promise<LoginSessionPayload> {
  const res = await apiFetch("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail || "Login failed");
  }
  const data = (await res.json()) as LoginSessionPayload & AuthTokens;
  if (data.access && data.refresh) {
    setAuthTokens(data.access, data.refresh);
  }
  if (data.role !== "CLIENT") {
    throw new Error("This account is not a client login. Use Designer or Admin portals.");
  }
  return data;
}

export { authMe, logoutDesigner as logoutClient };

export async function listClientRfpSessions(): Promise<ClientRfpSessionSummary[]> {
  const res = await apiFetch("/api/rfp/sessions/");
  if (!res.ok) return [];
  const data = (await res.json()) as { sessions?: ClientRfpSessionSummary[] };
  return data.sessions || [];
}

export async function fetchClientRfpSession(sessionId: string): Promise<ClientRfpSessionDetail | null> {
  const res = await apiFetch(`/api/rfp/${sessionId}/`);
  if (!res.ok) return null;
  const data = (await res.json()) as ClientRfpSessionDetail;
  return data;
}

export function isClientSessionCompleted(status: string): boolean {
  return status === "PROPOSAL_RENDERED" || status === "BOOKED";
}
