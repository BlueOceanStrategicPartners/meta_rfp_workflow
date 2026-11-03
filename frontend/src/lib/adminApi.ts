/**
 * Typed client for the Admin Command Center API (plan §6).
 * Every request goes through `apiFetch` (Bearer JWT, CSRF, refresh on 401).
 */
import { apiFetch } from "./apiClient";

const BASE = "/api/admin-center/";

/* ------------------------------------------------------------------ */
/* Errors                                                              */
/* ------------------------------------------------------------------ */

/** Fired on `window` whenever an admin call comes back 401/403 after the refresh. */
export const ADMIN_AUTH_ERROR_EVENT = "rfp-admin-auth-error";

export class AdminAuthError extends Error {
  readonly status: number;
  constructor(status: number, message = "Your session ended. Sign in again.") {
    super(message);
    this.name = "AdminAuthError";
    this.status = status;
  }
}

export type AdminFieldErrors = Record<string, unknown>;

export class AdminApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly errors?: AdminFieldErrors;
  readonly alternatives?: unknown[];
  constructor(
    status: number,
    detail: string,
    extra: { errors?: AdminFieldErrors; alternatives?: unknown[] } = {},
  ) {
    super(detail);
    this.name = "AdminApiError";
    this.status = status;
    this.detail = detail;
    this.errors = extra.errors;
    this.alternatives = extra.alternatives;
  }
}

/** First message for one field from a DRF-style `errors` object. */
export function fieldError(errors: AdminFieldErrors | undefined, key: string): string | null {
  if (!errors) return null;
  const v = errors[key];
  if (v === undefined || v === null) return null;
  if (Array.isArray(v)) return v.length ? String(v[0]) : null;
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Plain-language message for any thrown value. */
export function errorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (err instanceof AdminApiError || err instanceof AdminAuthError) return err.message || fallback;
  if (err instanceof TypeError) return "Can't reach the server. Check that the backend is running.";
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

function defaultDetail(status: number): string {
  if (status === 404) return "We couldn't find that. It may have been deleted.";
  if (status === 409) return "That can't be done right now because of its current state.";
  if (status === 413) return "That file is too large.";
  if (status >= 500) return "The server had a problem. Please try again in a moment.";
  return "That request didn't go through. Please check the details and try again.";
}

function firstErrorText(errors: AdminFieldErrors): string | null {
  for (const v of Object.values(errors)) {
    if (typeof v === "string" && v) return v;
    if (Array.isArray(v) && v.length && typeof v[0] === "string") return v[0];
  }
  return null;
}

async function parseError(res: Response): Promise<AdminApiError> {
  let detail = "";
  let errors: AdminFieldErrors | undefined;
  let alternatives: unknown[] | undefined;
  try {
    const body = (await res.json()) as unknown;
    if (body && typeof body === "object" && !Array.isArray(body)) {
      const b = body as Record<string, unknown>;
      if (typeof b.detail === "string") detail = b.detail;
      if (b.errors && typeof b.errors === "object") errors = b.errors as AdminFieldErrors;
      if (Array.isArray(b.alternatives)) alternatives = b.alternatives;
      // Plain DRF validation bodies ({field: ["msg"]}) without a wrapper.
      if (!detail && !errors && res.status === 400) errors = b;
      if (!detail && errors) detail = firstErrorText(errors) ?? "Please fix the highlighted fields.";
    }
  } catch {
    /* non-JSON body */
  }
  return new AdminApiError(res.status, detail || defaultDetail(res.status), { errors, alternatives });
}

function notifyAuthError(status: number) {
  if (typeof window === "undefined" || typeof window.dispatchEvent !== "function") return;
  try {
    window.dispatchEvent(new CustomEvent(ADMIN_AUTH_ERROR_EVENT, { detail: { status } }));
  } catch {
    /* ignore */
  }
}

type Query = Record<string, string | number | null | undefined>;

function buildUrl(path: string, query?: Query): string {
  const url = `${BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === null || v === undefined || v === "") continue;
    params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function request<T>(path: string, init: RequestInit = {}, query?: Query): Promise<T> {
  const res = await apiFetch(buildUrl(path, query), {
    ...init,
    headers: { Accept: "application/json", ...(init.headers as Record<string, string> | undefined) },
  });
  if (res.status === 401 || res.status === 403) {
    notifyAuthError(res.status);
    throw new AdminAuthError(res.status);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new AdminApiError(res.status, "The server sent a response we couldn't read.");
  }
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? "{}" : JSON.stringify(body),
});

/* ------------------------------------------------------------------ */
/* Types (plan §6, field names match the backend exactly)              */
/* ------------------------------------------------------------------ */

export type AuditEvent = {
  id?: string;
  action: string;
  actor: string | null;
  target_type?: string;
  target_id?: string;
  payload?: Record<string, unknown> | null;
  created_at: string;
};

export type AttentionItem = {
  rfp_id: string;
  company_name: string | null;
  reason: "escalated" | "amber_fields" | string;
};

export type OverviewData = {
  rfps: { total: number; by_status: Record<string, number> };
  sla: {
    target_seconds: number;
    measured: number;
    p50_seconds: number | null;
    p95_seconds: number | null;
    within_target_pct: number | null;
  };
  debate: { rounds: number; avg_consensus: number | null; partial_rate: number | null };
  pricing: { quotes: number; fallback_rate: number | null; model_trained: boolean };
  inventory: { properties: number; spaces: number; booked: number };
  occupancy: { rows: number; from: string | null; to: string | null };
  attention: AttentionItem[];
  recent_activity: AuditEvent[];
};

export type RfpListItem = {
  id: string;
  company_name: string | null;
  client_email: string | null;
  status: string;
  rounds: number;
  latest_consensus: number | null;
  amber_fields: string[];
  created_at: string;
  updated_at: string;
};

export type DebateFlag = {
  field_path: string;
  severity: string;
  message: string;
  expected?: string | null;
  actual?: string | null;
};

export type SourceCitation = { page_number?: number | null; verbatim_quote?: string | null };

export type ExtractedValue = { value: unknown; source_citation?: SourceCitation | null };

export type DebateRound = {
  iteration: number;
  extractor_model_id: string | null;
  critic_model_id: string | null;
  consensus: number | null;
  duration_ms: number | null;
  flags: DebateFlag[];
  extraction: Record<string, ExtractedValue | unknown>;
};

export type Quote = {
  id: string;
  floor: string | null;
  target: string | null;
  anchor: string | null;
  agreed: string | null;
  used_fallback: boolean;
  created_at: string;
};

export type QuoteWithRfp = Quote & { rfp_id: string; company_name: string | null };

export type RfpCards = {
  event_overview?: Record<string, unknown>;
  room_block?: Record<string, unknown>;
  meeting_space?: Record<string, unknown>;
  catering_av?: Record<string, unknown>;
  live_quote?: Record<string, unknown>;
  [section: string]: Record<string, unknown> | undefined;
};

export type RfpDetail = {
  id: string;
  status: string;
  company_name?: string | null;
  client_email: string | null;
  source_document_text: string | null;
  cards: RfpCards;
  amber_fields: string[];
  sla: { started_at: string | null; completed_at: string | null; duration_seconds: number | null };
  rounds: DebateRound[];
  quotes: Quote[];
  audit: AuditEvent[];
};

export const OVERRIDE_FIELDS = [
  "company_name",
  "event_type",
  "check_in_date",
  "check_out_date",
  "total_room_nights",
  "headcount",
  "seating_style",
] as const;
export type OverrideField = (typeof OVERRIDE_FIELDS)[number];

export type OverridePayload = {
  fields: Partial<Record<OverrideField, string | number>>;
  note?: string;
};

export type OverrideResult = {
  ok: boolean;
  quote?: {
    walk_away_floor_price?: string | number | null;
    optimal_target_price?: string | number | null;
    initial_anchor_price?: string | number | null;
  };
};

export type PricingPolicy = {
  walk_away_floor_margin_pct: number;
  max_autonomous_discount_pct: number;
  target_markup_pct: number;
  anchor_markup_pct: number;
  event_multiplier: number;
  seasonality_json: Record<string, number>;
  updated_by: string | null;
  updated_at: string | null;
};

export type PricingPolicyInput = Omit<PricingPolicy, "updated_by" | "updated_at">;

export type PricingModelStatus = {
  artifact_exists: boolean;
  trained_at: string | null;
  occupancy_rows: number;
  min_rows_required: number;
};

export type RetrainResult = { status: "ok" | "skipped_insufficient_data" | string; trained_at: string | null };

export type NegotiationItem = {
  id: string;
  company_name: string | null;
  status: string;
  taken_over: boolean;
  taken_over_by: string | null;
  check_in_date: string | null;
  check_out_date: string | null;
  headcount: number | null;
  latest_quote: {
    floor: string | null;
    target: string | null;
    anchor: string | null;
    agreed: string | null;
    used_fallback: boolean;
  } | null;
  updated_at: string;
};

/** One line of a negotiation: client, AI agent, an admin, the automatic holding reply, or a takeover marker. */
export type ConversationMessage = {
  who: "client" | "agent" | "admin" | "auto" | "system";
  by: string | null;
  text: string;
  at: string;
};

export type NegotiationConversation = {
  rfp_id: string;
  taken_over: boolean;
  messages: ConversationMessage[];
};

export type Property = { id: string; name: string; timezone: string; space_count: number };
export type PropertyInput = { name: string; timezone?: string };

export type Capacities = {
  banquet?: number;
  classroom?: number;
  theater?: number;
  u_shape?: number;
  cocktail?: number;
};

export type Space = {
  id: string;
  property: string;
  name: string;
  space_type: string;
  capacities_json: Capacities;
  rack_rate: string;
  base_floor_cost: string;
  av_capabilities_json: unknown;
  is_booked: boolean;
};

export type SpaceInput = {
  property: string;
  name: string;
  space_type: string;
  capacities_json: Capacities;
  rack_rate: string;
  base_floor_cost: string;
  av_capabilities_json?: unknown;
};

export type OccupancyRow = {
  id: string | number;
  property: string;
  target_date: string;
  room_occupancy_pct: number;
  hall_utilization_pct: number | null;
  adr: string;
  revpar: string;
  is_peak_season: boolean;
  local_event_multiplier: number | null;
};

export type OccupancyUploadReport = {
  created: number;
  updated: number;
  skipped: number;
  errors: { row: number; error: string }[];
};

export type DbSummary = {
  engine: string;
  vendor: string;
  tables: Record<string, number>;
  occupancy_range: { from: string | null; to: string | null } | null;
};

export type TelemetryData = {
  sla: {
    target_seconds: number;
    p50_seconds: number | null;
    p95_seconds: number | null;
    within_target_pct: number | null;
    recent: {
      rfp_id: string;
      company_name: string | null;
      status: string;
      duration_seconds: number | null;
      started_at: string | null;
    }[];
  };
  funnel: { status: string; count: number }[];
  conversion: { booked: number; total: number; rate: number | null };
  debate: {
    avg_rounds: number | null;
    avg_consensus: number | null;
    partial_rate: number | null;
    avg_critic_ms: number | null;
  };
  pricing: { quotes: number; fallback_rate: number | null };
  tokens: unknown | null;
};

/* ------------------------------------------------------------------ */
/* Endpoints                                                           */
/* ------------------------------------------------------------------ */

// Overview
export const getOverview = () => request<OverviewData>("overview/");

// Module 2 — Debate Observatory
export const listRfps = (params: { status?: string; q?: string } = {}) =>
  request<RfpListItem[]>("rfps/", {}, params);
export const getRfp = (id: string) => request<RfpDetail>(`rfps/${encodeURIComponent(id)}/`);
export const overrideRfp = (id: string, body: OverridePayload) =>
  request<OverrideResult>(`rfps/${encodeURIComponent(id)}/override/`, json("POST", body));

// Module 3 — Pricing
export const getPricingPolicy = () => request<PricingPolicy>("pricing/policy/");
export const savePricingPolicy = (body: PricingPolicyInput) =>
  request<PricingPolicy>("pricing/policy/", json("PUT", body));
export const getPricingModel = () => request<PricingModelStatus>("pricing/model/");
export const retrainPricingModel = () => request<RetrainResult>("pricing/retrain/", json("POST"));
export const listQuotes = (params: { rfp?: string } = {}) =>
  request<QuoteWithRfp[]>("pricing/quotes/", {}, params);

// Module 4 — Negotiations
export const listNegotiations = () => request<NegotiationItem[]>("negotiations/");
export const takeOverNegotiation = (id: string) =>
  request<unknown>(`negotiations/${encodeURIComponent(id)}/takeover/`, json("POST"));
export const releaseNegotiation = (id: string) =>
  request<unknown>(`negotiations/${encodeURIComponent(id)}/release/`, json("POST"));
export const sendNegotiationMessage = (id: string, text: string) =>
  request<unknown>(`negotiations/${encodeURIComponent(id)}/message/`, json("POST", { text }));
export const getNegotiationConversation = (id: string) =>
  request<NegotiationConversation>(`negotiations/${encodeURIComponent(id)}/conversation/`);

// Module 5 — Inventory
export const listProperties = () => request<Property[]>("inventory/properties/");
export const createProperty = (body: PropertyInput) =>
  request<Property>("inventory/properties/", json("POST", body));
export const updateProperty = (id: string, body: Partial<PropertyInput>) =>
  request<Property>(`inventory/properties/${encodeURIComponent(id)}/`, json("PATCH", body));
export const deleteProperty = (id: string) =>
  request<void>(`inventory/properties/${encodeURIComponent(id)}/`, { method: "DELETE" });

export const listSpaces = (params: { property?: string } = {}) =>
  request<Space[]>("inventory/spaces/", {}, params);
export const createSpace = (body: SpaceInput) => request<Space>("inventory/spaces/", json("POST", body));
export const updateSpace = (id: string, body: Partial<SpaceInput>) =>
  request<Space>(`inventory/spaces/${encodeURIComponent(id)}/`, json("PATCH", body));
export const deleteSpace = (id: string) =>
  request<void>(`inventory/spaces/${encodeURIComponent(id)}/`, { method: "DELETE" });
export const releaseSpace = (id: string) =>
  request<Space>(`inventory/spaces/${encodeURIComponent(id)}/release/`, json("POST"));

// Module 6 — Occupancy
export const listOccupancy = (params: { property?: string; from?: string; to?: string } = {}) =>
  request<OccupancyRow[]>("occupancy/", {}, params);
export function uploadOccupancy(file: File, property: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("property", property);
  return request<OccupancyUploadReport>("occupancy/upload/", { method: "POST", body: form });
}
export const getDbSummary = () => request<DbSummary>("occupancy/summary/");

// Module 7 — Telemetry
export const getTelemetry = () => request<TelemetryData>("telemetry/");

// Audit
export const listAudit = (params: { limit?: number; target_type?: string; target_id?: string } = {}) =>
  request<AuditEvent[]>("audit/", {}, params);
