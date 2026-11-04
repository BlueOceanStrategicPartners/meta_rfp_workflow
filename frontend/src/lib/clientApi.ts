import { apiFetch } from "./apiClient";
import {
  clearLocalArchivedFlag,
  mergeLocalArchivedIntoSummaries,
  setLocalArchivedFlag,
} from "./clientSessionArchiveLocal";
import { setAuthTokens, type AuthTokens } from "./authTokens";
import { authMe, logoutDesigner, type LoginSessionPayload } from "./designerApi";

export type ClientRfpSessionSummary = {
  id: string;
  status: string;
  completed: boolean;
  archived?: boolean;
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

async function tryArchiveViaApi(sessionId: string, archived: boolean): Promise<ClientRfpSessionSummary | null> {
  const body = JSON.stringify({ archived });

  let res = await apiFetch(`/api/rfp/${sessionId}/archive/`, { method: "POST", body });
  if (res.ok) return (await res.json()) as ClientRfpSessionSummary;

  if (res.status === 404 || res.status === 405) {
    res = await apiFetch(`/api/rfp/${sessionId}/`, {
      method: "PATCH",
      body,
    });
    if (res.ok) return (await res.json()) as ClientRfpSessionSummary;
  }

  if (res.status === 404 || res.status === 405) {
    res = await apiFetch("/api/rfp/sessions/", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, archived }),
    });
    if (res.ok) return (await res.json()) as ClientRfpSessionSummary;
  }

  return null;
}

export async function listClientRfpSessions(): Promise<ClientRfpSessionSummary[]> {
  const res = await apiFetch("/api/rfp/sessions/");
  if (!res.ok) return [];
  const data = (await res.json()) as { sessions?: ClientRfpSessionSummary[] };
  return mergeLocalArchivedIntoSummaries(data.sessions || []);
}

export async function fetchClientRfpSession(sessionId: string): Promise<ClientRfpSessionDetail | null> {
  const res = await apiFetch(`/api/rfp/${sessionId}/`);
  if (!res.ok) return null;
  const data = (await res.json()) as ClientRfpSessionDetail;
  return data;
}

export async function setClientRfpSessionArchived(
  sessionId: string,
  archived: boolean,
  hint?: Pick<ClientRfpSessionSummary, "title" | "status" | "completed" | "updated_at" | "created_at" | "last_snippet" | "proposal_card">,
): Promise<{ summary: ClientRfpSessionSummary; persisted: boolean }> {
  const fromApi = await tryArchiveViaApi(sessionId, archived);
  if (fromApi) {
    clearLocalArchivedFlag(sessionId);
    return {
      persisted: true,
      summary: {
        ...fromApi,
        archived: typeof fromApi.archived === "boolean" ? fromApi.archived : archived,
      },
    };
  }

  setLocalArchivedFlag(sessionId, archived);
  return {
    persisted: false,
    summary: {
      id: sessionId,
      status: hint?.status ?? "PROPOSAL_RENDERED",
      completed: hint?.completed ?? true,
      archived,
      title: hint?.title ?? "Session",
      updated_at: hint?.updated_at ?? new Date().toISOString(),
      created_at: hint?.created_at ?? new Date().toISOString(),
      last_snippet: hint?.last_snippet ?? "",
      proposal_card: hint?.proposal_card ?? null,
    },
  };
}

export function isClientSessionCompleted(status: string): boolean {
  return status === "PROPOSAL_RENDERED" || status === "BOOKED";
}
