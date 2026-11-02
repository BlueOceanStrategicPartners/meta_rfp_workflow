import { apiFetch } from "./apiClient";
import { clearAuthTokens, setAuthTokens } from "./authTokens";

import type { AgentWorkPlanStep } from "./designerChatStream";

export type DesignerChatActionState = {
  partial_completion?: boolean;
  continuation_recommended?: boolean;
  remaining_items?: string[];
  progress_completed?: Array<{ id: string; label: string; ok: boolean }>;
  clarification_options?: string[];
  agent_todos?: AgentWorkPlanStep[];
  /** User closed the Continue / action card — do not restore on reload. */
  dismissed?: boolean;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  ts?: string;
  action_state?: DesignerChatActionState;
};

export type TemplateRevision = {
  saved_at: string;
  note: string;
  name: string;
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
};

export type DesignerMediaAsset = {
  id: string;
  url: string;
  original_name: string;
  media_type: "IMAGE" | "VIDEO";
  metadata_json: Record<string, unknown>;
  width?: number | null;
  height?: number | null;
  created_at?: string;
};

export type ProposalTemplate = {
  id: string;
  name: string;
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
  is_default: boolean;
  chat_history_json: ChatMessage[];
  revision_history_json?: TemplateRevision[];
  updated_at: string;
  created_at?: string;
};

export async function authMe() {
  const res = await apiFetch("/api/auth/me/");
  return res.json();
}

export type DesignerLiveProgress = {
  active: boolean;
  agent_todos?: AgentWorkPlanStep[];
  work_plan?: AgentWorkPlanStep[];
  tool_steps?: Array<{ tool?: string; label?: string; ok?: boolean; phase?: string }>;
  preview?: { html_markup?: string; css_stylesheet?: string; js_script?: string };
};

/** Poll fallback while SSE POST stream is buffered in some browsers. */
export async function fetchDesignerLiveProgress(): Promise<DesignerLiveProgress> {
  const res = await apiFetch("/api/designer/chat/live-progress/");
  if (!res.ok) {
    return { active: false, agent_todos: [], work_plan: [], tool_steps: [] };
  }
  return res.json() as Promise<DesignerLiveProgress>;
}

export type LoginSessionPayload = {
  email: string;
  role: string;
  id: string;
  access: string;
  refresh: string;
};

export async function loginDesigner(
  email: string,
  password: string,
): Promise<LoginSessionPayload> {
  const res = await apiFetch("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({
      email: email.trim().toLowerCase(),
      password: password,
    }),
  });
  if (!res.ok) {
    let detail = "Invalid email or password.";
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = String(body.detail);
    } catch {
      if (res.status === 403) {
        detail = "Login blocked (CSRF). Refresh the page and try again.";
      } else if (res.status >= 500 || res.status === 502 || res.status === 504) {
        detail =
          "API server error (HTTP " +
          res.status +
          "). The backend on port 8000 may have crashed during autoreload — restart scripts/dev-backend.ps1 and try again.";
      } else if (res.status === 0 || res.type === "opaque") {
        detail = "Cannot reach the API. Run the dev backend and use http://127.0.0.1:5173.";
      }
    }
    throw new Error(detail);
  }
  const data = (await res.json()) as LoginSessionPayload;
  if (data.access && data.refresh) {
    setAuthTokens(data.access, data.refresh);
  }
  return data;
}

export async function logoutDesigner() {
  try {
    await apiFetch("/api/auth/logout/", { method: "POST", body: "{}" });
  } finally {
    clearAuthTokens();
  }
}

export async function listTemplates(): Promise<ProposalTemplate[]> {
  const res = await apiFetch("/api/designer/templates/");
  if (!res.ok) throw new Error("Failed to load templates");
  return res.json();
}

export async function listMediaAssets(templateId?: string | null): Promise<DesignerMediaAsset[]> {
  const qs = templateId ? `?template_id=${encodeURIComponent(templateId)}` : "";
  const res = await apiFetch(`/api/designer/assets/${qs}`);
  if (!res.ok) throw new Error("Failed to load media");
  return res.json();
}

export async function uploadDesignerAsset(file: File, templateId?: string | null) {
  const form = new FormData();
  form.append("file", file);
  if (templateId) form.append("template_id", templateId);
  const res = await apiFetch("/api/designer/assets/upload/", { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json() as Promise<DesignerMediaAsset>;
}

function formatApiError(err: unknown, fallback: string): string {
  if (typeof err === "string") return err;
  if (err && typeof err === "object") {
    const o = err as Record<string, unknown>;
    if (typeof o.detail === "string") return o.detail;
    if (Array.isArray(o.detail)) return o.detail.map(String).join("; ");
    const parts: string[] = [];
    for (const [key, val] of Object.entries(o)) {
      if (Array.isArray(val)) parts.push(`${key}: ${val.join(", ")}`);
      else if (typeof val === "string") parts.push(val);
    }
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

export async function saveTemplate(payload: Partial<ProposalTemplate> & { name: string }) {
  const res = await apiFetch("/api/designer/templates/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(formatApiError(err, "Save failed"));
  }
  return res.json();
}

export async function updateTemplate(id: string, payload: Partial<ProposalTemplate>) {
  const res = await apiFetch(`/api/designer/templates/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(formatApiError(err, "Update failed"));
  }
  return res.json();
}

export async function deleteTemplate(id: string) {
  const res = await apiFetch(`/api/designer/templates/${id}/`, { method: "DELETE" });
  if (!res.ok) throw new Error("Delete failed");
}

export async function duplicateTemplate(id: string) {
  const res = await apiFetch(`/api/designer/templates/${id}/duplicate/`, {
    method: "POST",
    body: "{}",
  });
  if (!res.ok) throw new Error("Duplicate failed");
  return res.json() as Promise<ProposalTemplate>;
}

export async function restoreRevision(id: string, index: number) {
  const res = await apiFetch(`/api/designer/templates/${id}/restore-revision/`, {
    method: "POST",
    body: JSON.stringify({ index }),
  });
  if (!res.ok) throw new Error("Restore failed");
  return res.json() as Promise<ProposalTemplate>;
}

export async function exportTemplateBundle(id: string) {
  const res = await apiFetch(`/api/designer/templates/${id}/export/`);
  if (!res.ok) throw new Error("Export failed");
  return res.json();
}

export type DesignerChatResponse = {
  assistant_message: string;
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
  clarification_options?: string[];
  history: ChatMessage[];
  used_fixture: boolean;
  map_stage_applied?: boolean;
  venue_map_id?: string;
  venue_map_title?: string;
  validation_warnings?: string[];
  self_check?: { valid: boolean; issues: string[]; repair_passes?: number };
  venue_maps_action?: string;
  venue_maps?: Array<{
    id: string;
    title: string;
    is_default: boolean;
    updated_at: string;
    revision_count: number;
  }>;
  preview_audit_findings?: Array<{ code: string; message: string; severity: string }>;
  attachment_required?: boolean;
  preview_automation_used?: boolean;
  request_preview_automation?: boolean;
  work_plan?: AgentWorkPlanStep[];
  agent_todos?: AgentWorkPlanStep[];
  agent_mode?: string;
  tool_steps?: number;
  tool_trace?: Array<Record<string, unknown>>;
  tool_loop_exhausted?: boolean;
  continuation_recommended?: boolean;
  partial_completion?: boolean;
  remaining_items?: string[];
  progress_completed?: Array<{ id: string; label: string; ok: boolean }>;
  model_api_error?: boolean;
};

export type PreviewAutomationReport = {
  ok: boolean;
  error?: string;
  duration_ms: number;
  viewport: { w: number; h: number };
  scroll: { docHeight: number; canScroll: boolean };
  elements: {
    heroVisible: boolean;
    ctaVisible: boolean;
    mapPopupOpenOnLoad: boolean;
    mapZoneCount: number;
  };
  interactions: Array<{ action: string; ok: boolean; detail?: string }>;
};

export async function auditDesignerPreview(html_markup: string, css_stylesheet: string, js_script: string) {
  const res = await apiFetch("/api/designer/preview-audit/", {
    method: "POST",
    body: JSON.stringify({ html_markup, css_stylesheet, js_script }),
  });
  if (!res.ok) throw new Error("Preview audit failed");
  return res.json() as Promise<{ findings: Array<{ code: string; message: string; severity: string }> }>;
}

export async function designerChat(body: {
  message: string;
  history: ChatMessage[];
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
  attachment_ids?: string[];
  template_id?: string;
  include_preview_audit?: boolean;
  preview_automation_report?: PreviewAutomationReport | null;
  preview_automation_depth?: number;
}): Promise<DesignerChatResponse> {
  const res = await apiFetch("/api/designer/chat/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}

export async function validateTemplate(
  html_markup: string,
  css_stylesheet: string,
  js_script: string
) {
  const res = await apiFetch("/api/designer/validate/", {
    method: "POST",
    body: JSON.stringify({ html_markup, css_stylesheet, js_script }),
  });
  if (!res.ok) throw new Error("Validation request failed");
  return res.json();
}

export async function previewTemplate(
  html_markup: string,
  css_stylesheet: string,
  js_script: string
) {
  const res = await apiFetch("/api/designer/preview/", {
    method: "POST",
    body: JSON.stringify({ html_markup, css_stylesheet, js_script }),
  });
  if (!res.ok) throw new Error("Preview request failed");
  return res.json();
}

export type DefaultVenueMapDesignerPayload = {
  available: boolean;
  detail?: string;
  id?: string;
  title?: string;
  locations?: { id: string; label: string; description?: string }[];
  agent_context?: string;
  map_section_snippet?: string;
  map_slot_css?: string;
};

export async function fetchDesignerDefaultVenueMap(): Promise<DefaultVenueMapDesignerPayload> {
  const res = await apiFetch("/api/designer/default-venue-map/");
  if (!res.ok) throw new Error("Failed to load default venue map");
  return res.json();
}

export async function injectDefaultVenueMapIntoTemplate(
  html_markup: string,
  css_stylesheet: string,
): Promise<{
  html_markup: string;
  css_stylesheet: string;
  default_map: DefaultVenueMapDesignerPayload;
}> {
  const res = await apiFetch("/api/designer/inject-default-venue-map/", {
    method: "POST",
    body: JSON.stringify({ html_markup, css_stylesheet }),
  });
  if (!res.ok) throw new Error("Could not insert default venue map slot");
  return res.json();
}

export async function removeVenueMapSlotFromProposal(html_markup: string, css_stylesheet: string) {
  const res = await apiFetch("/api/designer/remove-venue-map-slot/", {
    method: "POST",
    body: JSON.stringify({ html_markup, css_stylesheet }),
  });
  if (!res.ok) throw new Error("Could not remove map from proposal");
  return res.json() as Promise<{ html_markup: string; css_stylesheet: string }>;
}

export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export { REQUIRED_PLACEHOLDERS } from "./designerPlaceholders";
