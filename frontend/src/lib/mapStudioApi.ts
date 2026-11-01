import type { ChatMessage, DesignerMediaAsset } from "./designerApi";
import { authMe, loginDesigner, logoutDesigner } from "./designerApi";
import { apiFetch } from "./apiClient";

export type { ChatMessage };

export type MapLocation = {
  id: string;
  location_id?: string;
  label: string;
  description?: string;
  image_urls?: string[];
};

export type MapRevision = {
  saved_at: string;
  note: string;
  title: string;
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
};

export type VenueMapRecord = {
  id: string;
  title: string;
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
  is_default: boolean;
  is_verified: boolean;
  chat_history_json: ChatMessage[];
  revision_history_json?: MapRevision[];
  zones?: MapLocation[];
  updated_at: string;
};

export async function mapAuthMe() {
  const me = await authMe();
  const ok = Boolean(
    me.authenticated && (me.role === "DESIGNER" || me.role === "ADMIN")
  );
  return { ...me, mapStudioAuthed: ok };
}

export { loginDesigner as loginMapStudio, logoutDesigner as logoutMapStudio };

export async function listVenueMaps(): Promise<VenueMapRecord[]> {
  const res = await apiFetch("/api/maps/");
  if (!res.ok) throw new Error("Failed to load maps");
  return res.json();
}

export async function listMapMedia(venueMapId?: string | null): Promise<DesignerMediaAsset[]> {
  const qs = venueMapId ? `?venue_map_id=${encodeURIComponent(venueMapId)}` : "";
  const res = await apiFetch(`/api/maps/assets/${qs}`);
  if (!res.ok) throw new Error("Failed to load media");
  return res.json();
}

function formatApiError(err: unknown, fallback: string): string {
  if (typeof err === "string") return err;
  if (err && typeof err === "object") {
    const o = err as Record<string, unknown>;
    if (typeof o.detail === "string") return o.detail;
    const parts: string[] = [];
    for (const [key, val] of Object.entries(o)) {
      if (Array.isArray(val)) parts.push(`${key}: ${val.join(", ")}`);
      else if (typeof val === "string") parts.push(val);
    }
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

export async function saveVenueMap(payload: Partial<VenueMapRecord> & { title: string; locations?: MapLocation[] }) {
  const res = await apiFetch("/api/maps/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(formatApiError(err, "Save failed"));
  }
  return res.json();
}

export async function updateVenueMap(id: string, payload: Partial<VenueMapRecord> & { locations?: MapLocation[] }) {
  const res = await apiFetch(`/api/maps/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(formatApiError(err, "Update failed"));
  }
  return res.json();
}

export async function deleteVenueMap(id: string) {
  const res = await apiFetch(`/api/maps/${id}/`, { method: "DELETE" });
  if (!res.ok) throw new Error("Delete failed");
}

export async function duplicateVenueMap(id: string) {
  const res = await apiFetch(`/api/maps/${id}/duplicate/`, { method: "POST", body: "{}" });
  if (!res.ok) throw new Error("Duplicate failed");
  return res.json() as Promise<VenueMapRecord>;
}

export async function restoreMapRevision(id: string, index: number) {
  const res = await apiFetch(`/api/maps/${id}/restore-revision/`, {
    method: "POST",
    body: JSON.stringify({ index }),
  });
  if (!res.ok) throw new Error("Restore failed");
  return res.json() as Promise<VenueMapRecord>;
}

export async function exportVenueMapBundle(id: string) {
  const res = await apiFetch(`/api/maps/${id}/export/`);
  if (!res.ok) throw new Error("Export failed");
  return res.json();
}

export type MapChatResponse = {
  assistant_message: string;
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
  locations?: MapLocation[];
  clarification_options?: string[];
  history: ChatMessage[];
  used_fixture: boolean;
};

export async function mapStudioChat(body: {
  message: string;
  history: ChatMessage[];
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
  attachment_ids?: string[];
  venue_map_id?: string;
}): Promise<MapChatResponse> {
  const res = await apiFetch("/api/maps/chat/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}

export async function validateVenueMap(
  html_markup: string,
  css_stylesheet: string,
  js_script: string,
  locations: MapLocation[] = []
) {
  const res = await apiFetch("/api/maps/validate/", {
    method: "POST",
    body: JSON.stringify({ html_markup, css_stylesheet, js_script, locations }),
  });
  if (!res.ok) throw new Error("Validation request failed");
  return res.json();
}

export async function previewVenueMap(html_markup: string, css_stylesheet: string, js_script: string) {
  const res = await apiFetch("/api/maps/preview/", {
    method: "POST",
    body: JSON.stringify({ html_markup, css_stylesheet, js_script }),
  });
  if (!res.ok) throw new Error("Preview request failed");
  return res.json();
}

export type PublishedVenueMap = {
  id: string;
  title: string;
  compiled_html: string;
  locations: MapLocation[];
};

export async function fetchPublishedVenueMap(): Promise<PublishedVenueMap | null> {
  const res = await apiFetch("/api/maps/published/");
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to load venue map");
  return res.json();
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
