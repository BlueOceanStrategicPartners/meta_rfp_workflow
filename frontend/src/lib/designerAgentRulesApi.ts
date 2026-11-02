import { apiFetch } from "./apiClient";

export type DesignerAgentRule = {
  id: string;
  sort_order: number;
  body: string;
  created_at: string;
  updated_at: string;
};

export type RuleValidateResult = {
  has_conflict: boolean;
  explanation: string;
  conflicting_rule_ids: string[];
  suggested_rule: string;
};

function formatApiErrorBody(body: unknown, fallback: string): string {
  if (typeof body === "string") return body;
  if (body && typeof body === "object") {
    const o = body as Record<string, unknown>;
    if (typeof o.detail === "string") return o.detail;
    if (Array.isArray(o.detail)) return o.detail.map(String).join("; ");
    if (o.code === "agent_rules_schema_missing") {
      return "Agent rules database is not ready. Restart the dev backend (migrations run on startup) or run: python manage.py migrate";
    }
  }
  return fallback;
}

async function apiErrorFromResponse(res: Response, fallback: string): Promise<Error> {
  if (res.status === 401 || res.status === 403) {
    return new Error("Sign in as a designer to manage agent rules.");
  }
  if (res.status >= 502 && res.status <= 504) {
    return new Error("API server unavailable. Start the backend on port 8000 and try again.");
  }
  try {
    const body = await res.json();
    return new Error(formatApiErrorBody(body, fallback));
  } catch {
    if (res.status >= 500) {
      return new Error("Server error loading agent rules. Check the backend console.");
    }
    return new Error(fallback);
  }
}

export async function listDesignerAgentRules(): Promise<DesignerAgentRule[]> {
  const res = await apiFetch("/api/designer/agent-rules/");
  if (!res.ok) throw await apiErrorFromResponse(res, "Could not load agent rules.");
  const data = (await res.json()) as unknown;
  return Array.isArray(data) ? data : [];
}

export async function createDesignerAgentRule(body: string, sort_order = 0): Promise<DesignerAgentRule> {
  const res = await apiFetch("/api/designer/agent-rules/", {
    method: "POST",
    body: JSON.stringify({ body, sort_order }),
  });
  if (!res.ok) throw await apiErrorFromResponse(res, "Could not add rule.");
  return res.json();
}

export async function updateDesignerAgentRule(
  id: string,
  patch: { body?: string; sort_order?: number },
): Promise<DesignerAgentRule> {
  const res = await apiFetch(`/api/designer/agent-rules/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw await apiErrorFromResponse(res, "Could not update rule.");
  return res.json();
}

export async function deleteDesignerAgentRule(id: string): Promise<void> {
  const res = await apiFetch(`/api/designer/agent-rules/${id}/`, { method: "DELETE" });
  if (!res.ok) throw await apiErrorFromResponse(res, "Could not delete rule.");
}

export async function validateDesignerAgentRule(
  body: string,
  excludeRuleId?: string,
): Promise<RuleValidateResult> {
  const res = await apiFetch("/api/designer/agent-rules/validate/", {
    method: "POST",
    body: JSON.stringify({ body, exclude_rule_id: excludeRuleId }),
  });
  if (!res.ok) throw await apiErrorFromResponse(res, "Validation failed.");
  return res.json();
}
