/**
 * Formatting helpers for the Admin Command Center.
 * Pure functions only, so they can be unit-tested without a DOM.
 */

export const RFP_STATUSES = [
  "EXTRACTING",
  "DEBATING",
  "AWAITING_USER_CARD_EDIT",
  "PRICING",
  "NEGOTIATING",
  "PROPOSAL_RENDERED",
  "BOOKED",
  "ESCALATED",
] as const;

export type RfpStatus = (typeof RFP_STATUSES)[number];

export type StatusTone = "violet" | "sky" | "emerald" | "indigo" | "green" | "amber" | "slate";

export type StatusMeta = {
  /** Short label used on chips. Shared statuses (e.g. EXTRACTING/DEBATING) share a label. */
  label: string;
  /** Distinct per-status step name, used where every status needs its own row (funnel). */
  step: string;
  tone: StatusTone;
};

const STATUS_META: Record<RfpStatus, StatusMeta> = {
  EXTRACTING: { label: "In debate", step: "Reading request", tone: "violet" },
  DEBATING: { label: "In debate", step: "Checking details", tone: "violet" },
  AWAITING_USER_CARD_EDIT: { label: "Awaiting client", step: "Awaiting client", tone: "sky" },
  PRICING: { label: "Negotiating", step: "Pricing", tone: "emerald" },
  NEGOTIATING: { label: "Negotiating", step: "Negotiating", tone: "emerald" },
  PROPOSAL_RENDERED: { label: "Proposal sent", step: "Proposal sent", tone: "indigo" },
  BOOKED: { label: "Booked", step: "Booked", tone: "green" },
  ESCALATED: { label: "Human takeover", step: "Human takeover", tone: "amber" },
};

function humanize(raw: string): string {
  const words = raw.toLowerCase().replace(/[_-]+/g, " ").trim();
  if (!words) return "Unknown";
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** One fixed mapping so the same status looks the same everywhere. */
export function statusMeta(status: string | null | undefined): StatusMeta {
  const key = String(status || "").toUpperCase() as RfpStatus;
  const known = STATUS_META[key];
  if (known) return known;
  const label = humanize(String(status || ""));
  return { label, step: label, tone: "slate" };
}

/** Statuses an admin can take over from (mirrors the backend rule in plan §6.4). */
export const TAKEOVER_STATUSES: readonly string[] = [
  "AWAITING_USER_CARD_EDIT",
  "PRICING",
  "NEGOTIATING",
  "PROPOSAL_RENDERED",
];

export const EMPTY = "—";

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

const moneyFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/** Money has no currency field in the backend, so no symbol: "28,560". */
export function formatMoney(value: string | number | null | undefined): string {
  const n = toNumber(value);
  return n === null ? EMPTY : moneyFormatter.format(n);
}

/** Fractions to percent with one decimal place: 0.12 → "12.0%". */
export function formatPct(fraction: number | string | null | undefined, digits = 1): string {
  const n = toNumber(fraction);
  if (n === null) return EMPTY;
  return `${(n * 100).toFixed(digits)}%`;
}

/** Plain number with fixed decimals, or "—". */
export function formatNumber(value: number | string | null | undefined, digits = 1): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  return n.toFixed(digits);
}

/** Seconds to a short human duration: 13.9 → "13.9 s", 125 → "2 min 5 s". */
export function formatDuration(seconds: number | string | null | undefined): string {
  const n = toNumber(seconds);
  if (n === null || n < 0) return EMPTY;
  if (n < 60) return `${n.toFixed(1)} s`;
  const totalSeconds = Math.round(n);
  if (totalSeconds < 3600) {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return s ? `${m} min ${s} s` : `${m} min`;
  }
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** Milliseconds: 412 → "412 ms", 1500 → "1.5 s". */
export function formatMs(ms: number | string | null | undefined): string {
  const n = toNumber(ms);
  if (n === null || n < 0) return EMPTY;
  if (n < 1000) return `${Math.round(n)} ms`;
  return formatDuration(n / 1000);
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  // Bare dates (YYYY-MM-DD) are calendar days, so read them as local time, not UTC.
  const bare = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const d = bare ? new Date(Number(bare[1]), Number(bare[2]) - 1, Number(bare[3])) : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

const dateFormatter = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });
const dateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

/** "Dec 1, 2026" */
export function formatDate(value: string | null | undefined): string {
  const d = parseDate(value);
  return d ? dateFormatter.format(d) : EMPTY;
}

/** "Dec 1, 3:04 PM" */
export function formatDateTime(value: string | null | undefined): string {
  const d = parseDate(value);
  return d ? dateTimeFormatter.format(d) : EMPTY;
}

/** "Dec 1, 2026 – Dec 4, 2026", tolerating a missing end. */
export function formatDateRange(from: string | null | undefined, to: string | null | undefined): string {
  if (!from && !to) return EMPTY;
  if (!to || from === to) return formatDate(from || to);
  return `${formatDate(from)} – ${formatDate(to)}`;
}

/** "just now", "5 min ago", "3 h ago", "2 d ago", then a calendar date. */
export function formatRelativeTime(value: string | null | undefined, now: number = Date.now()): string {
  const d = parseDate(value);
  if (!d) return EMPTY;
  const diffSec = Math.round((now - d.getTime()) / 1000);
  if (diffSec < 45) return "just now";
  const min = Math.round(diffSec / 60);
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} h ago`;
  const days = Math.round(h / 24);
  if (days < 30) return `${days} d ago`;
  return formatDate(value);
}

/** First 8 characters of a UUID, for compact tables. */
export function shortId(id: string | null | undefined): string {
  return id ? String(id).slice(0, 8) : EMPTY;
}

/** Turn an audit action ("pricing.policy.update") into a readable sentence fragment. */
const ACTION_LABELS: Record<string, string> = {
  "debate.override": "Overrode request details",
  "pricing.policy.update": "Updated pricing policy",
  "pricing.retrain": "Retrained pricing model",
  "negotiation.takeover": "Took over a negotiation",
  "negotiation.release": "Handed a negotiation back",
  "negotiation.message": "Sent a message to the client",
  "negotiation.turn": "Client conversation turn",
  "inventory.space.create": "Added a space",
  "inventory.space.update": "Edited a space",
  "inventory.space.delete": "Deleted a space",
  "inventory.space.release": "Released a booking",
  "inventory.property.create": "Added a property",
  "inventory.property.update": "Edited a property",
  "inventory.property.delete": "Deleted a property",
  "occupancy.upload": "Uploaded occupancy data",
};

export function actionLabel(action: string | null | undefined): string {
  if (!action) return "Activity";
  return ACTION_LABELS[action] ?? humanize(action.replace(/\./g, " "));
}

/* ------------------------------------------------------------------ */
/* Pricing policy maths (client-side example ladder + validation)      */
/* ------------------------------------------------------------------ */

export type PolicyNumbers = {
  walk_away_floor_margin_pct: number;
  max_autonomous_discount_pct: number;
  target_markup_pct: number;
  anchor_markup_pct: number;
  event_multiplier: number;
  seasonality_json: Record<string, number>;
};

/** Season multiplier for a month (1–12). Months not listed default to 1.0. */
export function seasonFor(seasonality: Record<string, number> | null | undefined, month: number): number {
  const v = seasonality?.[String(month)];
  return typeof v === "number" && Number.isFinite(v) ? v : 1;
}

export type LadderExample = {
  nights: number;
  rackRate: number;
  month: number;
  base: number;
  floor: number;
  target: number;
  anchor: number;
};

/**
 * Mirrors the backend fallback engine (plan §7.2):
 *   base   = rack × nights × season(month) × event_multiplier
 *   floor  = base × (1 + margin)
 *   target = base × (1 + target_markup)
 *   anchor = target × (1 + anchor_markup)
 * then the ladder is enforced: target ≥ floor × 1.05, anchor ≥ target × 1.03.
 */
/**
 * Same formula as the backend's simple-formula quote for a space-only booking:
 * floor = operating cost (space floor cost × nights) + margin;
 * target = rack rate × nights × season × event multiplier + goal markup.
 */
export function computeLadderExample(
  policy: PolicyNumbers,
  rackRate: number,
  nights = 3,
  month = 1,
  floorCost = 0,
): LadderExample {
  const base = rackRate * nights * seasonFor(policy.seasonality_json, month) * policy.event_multiplier;
  const floor = floorCost * nights * (1 + policy.walk_away_floor_margin_pct);
  let target = base * (1 + policy.target_markup_pct);
  let anchor = target * (1 + policy.anchor_markup_pct);
  if (target < floor * 1.05) target = floor * 1.05;
  if (anchor < target * 1.03) anchor = target * 1.03;
  return { nights, rackRate, month, base, floor, target, anchor };
}

export type PolicyErrors = Partial<Record<keyof PolicyNumbers | `season_${number}`, string>>;

/** Same rules as the backend serializer (plan §5.2), in plain words. */
export function validatePolicy(p: PolicyNumbers): PolicyErrors {
  const errors: PolicyErrors = {};
  const bad = (n: number) => !Number.isFinite(n);
  if (bad(p.walk_away_floor_margin_pct) || p.walk_away_floor_margin_pct < 0 || p.walk_away_floor_margin_pct > 1) {
    errors.walk_away_floor_margin_pct = "Use a value from 0% to 100%.";
  }
  if (bad(p.max_autonomous_discount_pct) || p.max_autonomous_discount_pct < 0 || p.max_autonomous_discount_pct > 0.5) {
    errors.max_autonomous_discount_pct = "Use a value from 0% to 50%.";
  }
  if (bad(p.target_markup_pct) || p.target_markup_pct < 0) {
    errors.target_markup_pct = "Use a value of 0% or more.";
  } else if (!errors.walk_away_floor_margin_pct && p.target_markup_pct <= p.walk_away_floor_margin_pct) {
    errors.target_markup_pct = "Must be higher than the floor margin, so the target stays above the floor.";
  }
  if (bad(p.anchor_markup_pct) || p.anchor_markup_pct < 0 || p.anchor_markup_pct > 1) {
    errors.anchor_markup_pct = "Use a value from 0% to 100%.";
  }
  if (bad(p.event_multiplier) || p.event_multiplier < 0.5 || p.event_multiplier > 3) {
    errors.event_multiplier = "Use a number from 0.5 to 3.0.";
  }
  for (let m = 1; m <= 12; m += 1) {
    const v = seasonFor(p.seasonality_json, m);
    const raw = p.seasonality_json?.[String(m)];
    if ((raw !== undefined && bad(raw)) || v < 0.5 || v > 3) {
      errors[`season_${m}`] = "Use 0.5 to 3.0.";
    }
  }
  return errors;
}

export const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

export const MONTH_SHORT = MONTH_NAMES.map((m) => m.slice(0, 3));

/** Read the `{detail, alternatives}` style message into plain text for the override form. */
export function overCapacityMessage(detail: string, alternativeNames: string[]): string {
  if (!alternativeNames.length) return detail;
  return `${detail} Try: ${alternativeNames.join(", ")}.`;
}

/** Space type labels. */
export const SPACE_TYPES = ["ROOM_BLOCK", "BALLROOM", "BOARDROOM", "OUTDOOR"] as const;
export type SpaceType = (typeof SPACE_TYPES)[number];

const SPACE_TYPE_LABELS: Record<SpaceType, string> = {
  ROOM_BLOCK: "Room block",
  BALLROOM: "Ballroom",
  BOARDROOM: "Boardroom",
  OUTDOOR: "Outdoor",
};

export function spaceTypeLabel(t: string | null | undefined): string {
  if (!t) return EMPTY;
  return SPACE_TYPE_LABELS[t as SpaceType] ?? humanize(t);
}

/* ------------------------------------------------------------------ */
/* Source highlighting (debate detail)                                 */
/* ------------------------------------------------------------------ */

/** Every `verbatim_quote` string found anywhere inside an extraction payload. */
export function collectQuotes(value: unknown, out: Set<string> = new Set(), depth = 0): Set<string> {
  if (depth > 8 || value === null || value === undefined) return out;
  if (Array.isArray(value)) {
    for (const v of value) collectQuotes(v, out, depth + 1);
    return out;
  }
  if (typeof value === "object") {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (k === "verbatim_quote" && typeof v === "string" && v.trim()) out.add(v.trim());
      else collectQuotes(v, out, depth + 1);
    }
  }
  return out;
}

export type TextSegment = { text: string; mark: boolean };

/** Split `text` into plain and highlighted parts for each quote (case-insensitive, overlaps merged). */
export function highlightSegments(text: string, quotes: Iterable<string>): TextSegment[] {
  if (!text) return [];
  const lower = text.toLowerCase();
  const ranges: [number, number][] = [];
  for (const q of quotes) {
    const needle = q.trim().toLowerCase();
    if (needle.length < 3) continue;
    let from = 0;
    for (;;) {
      const idx = lower.indexOf(needle, from);
      if (idx === -1) break;
      ranges.push([idx, idx + needle.length]);
      from = idx + needle.length;
    }
  }
  if (!ranges.length) return [{ text, mark: false }];
  ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  const out: TextSegment[] = [];
  let pos = 0;
  for (const [s, e] of merged) {
    if (s > pos) out.push({ text: text.slice(pos, s), mark: false });
    out.push({ text: text.slice(s, e), mark: true });
    pos = e;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), mark: false });
  return out;
}

/** Display any extracted value as short text. */
export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return EMPTY;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    const s = JSON.stringify(value);
    return s.length > 160 ? `${s.slice(0, 157)}…` : s;
  } catch {
    return String(value);
  }
}

/** "total_room_nights" → "Total room nights" */
export function fieldLabel(path: string): string {
  return humanize(path.split(".").pop() || path);
}
