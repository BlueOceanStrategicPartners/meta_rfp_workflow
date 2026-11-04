/**
 * Pricing-model and "Why this price?" helpers for the admin Pricing and Occupancy pages
 * (XGBoost plan §3 D3, §8, §9). Pure functions only, so they can be unit-tested without a DOM.
 */
import type {
  FeatureImportance,
  Money,
  OccupancySource,
  PricingMetrics,
  PricingModelStatus,
  QuoteExplanationInputs,
  QuoteExplanationStep,
  RetrainResult,
} from "./adminApi";
import { EMPTY, formatDate, formatDateTime, formatMoney, type StatusTone } from "./adminFormat";

function num(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

const countFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/** Whole-number count with separators: 1095 → "1,095". */
export function formatCount(value: number | string | null | undefined): string {
  const n = num(value);
  return n === null ? EMPTY : countFormatter.format(n);
}

/** "1 day" / "1,095 days". */
export function formatDays(value: number | string | null | undefined): string {
  const n = num(value);
  if (n === null) return EMPTY;
  return `${formatCount(n)} ${n === 1 ? "day" : "days"}`;
}

function parseDay(value: string | null | undefined): Date | null {
  if (!value) return null;
  const bare = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  const d = bare ? new Date(Number(bare[1]), Number(bare[2]) - 1, Number(bare[3])) : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

const monthYearFormatter = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" });

/** "Nov 2023 – Oct 2026"; one month if both ends fall in it; "" when unknown. */
export function formatMonthRange(from: string | null | undefined, to: string | null | undefined): string {
  const a = parseDay(from);
  const b = parseDay(to);
  if (!a && !b) return "";
  if (!a || !b) return monthYearFormatter.format((a ?? b)!);
  const left = monthYearFormatter.format(a);
  const right = monthYearFormatter.format(b);
  return left === right ? left : `${left} – ${right}`;
}

/**
 * A model metric as a percent number. The training code sends `mape` and `improvement_pct`
 * already multiplied by 100 (4.12 = 4.12%), so this only parses; it never rescales.
 */
export function metricPct(value: number | string | null | undefined): number | null {
  return num(value);
}

/** Percent number to short text: 4.12 → "4.1%", 23.4 → "23%", 4 → "4%". */
export function formatPlainPct(percent: number | null | undefined): string {
  if (percent === null || percent === undefined || !Number.isFinite(percent)) return EMPTY;
  const abs = Math.abs(percent);
  const rounded = abs >= 10 ? Math.round(percent) : Math.round(percent * 10) / 10;
  return `${String(rounded)}%`;
}

/* ------------------------------------------------------------------ */
/* Model card                                                          */
/* ------------------------------------------------------------------ */

export type ModelState = "none" | "active" | "inactive";

export type ModelStatusSummary = {
  state: ModelState;
  chip: { label: string; tone: StatusTone };
  /** The plain-words status line. */
  headline: string;
  /** Version and training time, e.g. "Version 3 · trained Nov 5, 3:04 PM". */
  detail: string | null;
};

const NOT_BETTER_REASONS = new Set([
  "model_not_better_than_baseline",
  "not_better_than_baseline",
  "inactive_not_better",
  "not_better",
]);

function humanizeCode(raw: string): string {
  const words = raw.replace(/[_-]+/g, " ").trim().toLowerCase();
  return words || raw;
}

/** "Model v3" / "v3" → "3", so labels never read "vv3". */
function versionText(version: number | string | null | undefined): string | null {
  if (version === null || version === undefined || version === "") return null;
  return String(version).replace(/^v(?=\d)/i, "");
}

/** The model card's status line in plain words (plan §9). */
export function modelStatusSummary(model: PricingModelStatus): ModelStatusSummary {
  const version = versionText(model.version);
  const detailParts: string[] = [];
  if (version) detailParts.push(`Version ${version}`);
  if (model.trained_at) detailParts.push(`trained ${formatDateTime(model.trained_at)}`);
  const detail = detailParts.length ? detailParts.join(" · ") : null;

  const trained = !!model.artifact_exists || !!version || !!model.trained_at;
  if (!trained) {
    return {
      state: "none",
      chip: { label: "Not trained", tone: "slate" },
      headline: "Not trained yet — quotes use the simple formula.",
      detail: null,
    };
  }

  if (model.is_active === false) {
    const reason = (model.inactive_reason ?? "").trim();
    const improvement = metricPct(model.metrics?.improvement_pct);
    const notBetter = reason
      ? NOT_BETTER_REASONS.has(reason.toLowerCase())
      : improvement !== null && improvement <= 0;
    let headline: string;
    if (notBetter) {
      headline = "Trained, but not better than a simple average — still using the simple formula.";
    } else if (!reason) {
      headline = "Trained, but not in use yet — quotes use the simple formula. Retrain to switch it on.";
    } else {
      const text = /\s/.test(reason) ? reason.replace(/[.\s]+$/, "") : humanizeCode(reason);
      headline = `Trained, but not in use (${text}) — still using the simple formula.`;
    }
    return { state: "inactive", chip: { label: "Not in use", tone: "amber" }, headline, detail };
  }

  const rows = num(model.rows_used);
  const range = formatMonthRange(model.date_from, model.date_to);
  const headline =
    rows !== null && rows > 0
      ? `Trained on ${formatDays(rows)}${range ? ` (${range})` : ""}.`
      : "Trained and in use.";
  return { state: "active", chip: { label: "In use", tone: "green" }, headline, detail };
}

export type ModelQuality = {
  /** "Typical error ±4.1%", or null when unknown. */
  error: string | null;
  /** "23% better than a simple average" / "Not better than a simple average", or null. */
  improvement: string | null;
  better: boolean | null;
};

/** Quality in plain words from the stored metrics. `null` when there are no metrics. */
export function modelQuality(metrics: PricingMetrics | null | undefined): ModelQuality | null {
  if (!metrics) return null;
  const mape = metricPct(metrics.mape);
  const imp = metricPct(metrics.improvement_pct);
  if (mape === null && imp === null) return null;
  const error = mape === null ? null : `Typical error ±${formatPlainPct(Math.abs(mape))}`;
  let improvement: string | null = null;
  let better: boolean | null = null;
  if (imp !== null) {
    better = imp > 0;
    improvement = better
      ? `${formatPlainPct(imp)} better than a simple average`
      : "Not better than a simple average";
  }
  return { error, improvement, better };
}

export type FactorBar = {
  feature: string;
  label: string;
  /** Share of the model's total importance, 0–1. */
  share: number;
  /** Bar width relative to the top factor, 0–100. */
  widthPct: number;
};

/** Top `n` factors for the "What drives demand" list, biggest first. */
export function topFactors(list: FeatureImportance[] | null | undefined, n = 5): FactorBar[] {
  const items = (list ?? [])
    .map((f) => ({ ...f, importance: num(f.importance) ?? 0 }))
    .filter((f) => f.importance > 0);
  if (!items.length) return [];
  items.sort((a, b) => b.importance - a.importance);
  const sum = items.reduce((s, f) => s + f.importance, 0);
  // Normalised importances (all ≤ 1, summing to ≤ 1) are already shares; raw gains are not.
  const alreadyShares = items.every((f) => f.importance <= 1) && sum <= 1.0001;
  const top = items[0].importance;
  return items.slice(0, n).map((f) => ({
    feature: f.feature,
    label: f.label?.trim() || humanizeCode(f.feature).replace(/^\w/, (c) => c.toUpperCase()),
    share: alreadyShares ? f.importance : f.importance / sum,
    widthPct: Math.min(100, (f.importance / top) * 100),
  }));
}

/** "1,095 days used for training · 120 app-generated days ignored". */
export function trainingDataLine(data: PricingModelStatus["data"]): string | null {
  if (!data) return null;
  const trainable = num(data.trainable) ?? 0;
  const generated = num(data.generated) ?? 0;
  const parts = [`${formatDays(trainable)} used for training`];
  if (generated > 0) parts.push(`${formatCount(generated)} app-generated ${generated === 1 ? "day" : "days"} ignored`);
  return parts.join(" · ");
}

export type Feedback = { message: string; tone: "success" | "warning" | "error" | "info" };

/** The snackbar after "Retrain model", one per result status. */
export function retrainFeedback(res: RetrainResult): Feedback {
  switch (res.status) {
    case "ok":
      return { message: "Model retrained. New quotes use it.", tone: "success" };
    case "skipped_insufficient_data": {
      const have = num(res.rows_available);
      const need = num(res.rows_required);
      const counts = have !== null && need !== null ? `: ${formatCount(have)} of ${formatCount(need)} days` : "";
      return {
        message: `Not enough history${counts}. Import more on the Occupancy page.`,
        tone: "warning",
      };
    }
    case "inactive_not_better":
      return {
        message:
          "The new model wasn't better than a simple average, so quotes keep using the simple formula. Import more history and try again.",
        tone: "warning",
      };
    case "error":
      return {
        message: res.detail?.trim() || "Retraining failed. Quotes keep using the simple formula.",
        tone: "error",
      };
    default:
      return { message: res.detail?.trim() || `Retraining finished (${humanizeCode(String(res.status))}).`, tone: "info" };
  }
}

/* ------------------------------------------------------------------ */
/* Engine labels                                                       */
/* ------------------------------------------------------------------ */

type EngineFields = {
  engine?: string | null;
  model_version?: number | string | null;
  used_fallback?: boolean | null;
};

/** True when the trained model priced the quote. Older rows only have `used_fallback`. */
export function usedModel(q: EngineFields): boolean {
  if (q.engine === "model") return true;
  if (q.engine === "fallback") return false;
  return q.used_fallback === false;
}

/** "Model v3", "Model", or "Simple formula". */
export function engineLabel(q: EngineFields): string {
  if (!usedModel(q)) return "Simple formula";
  const v = versionText(q.model_version);
  return v ? `Model v${v}` : "Model";
}

const FALLBACK_REASONS: Record<string, string> = {
  no_model: "No model trained yet",
  insufficient_history: "Not enough history",
  model_not_better_than_baseline: "Model not better than a simple average",
  prediction_out_of_bounds: "Model's estimate looked wrong",
  extreme_request: "Unusual request — needs review",
  model_error: "Model had a problem",
  dates_missing: "Dates not confirmed",
};

/** Why the simple formula was used, in plain words. Prefers the backend's own label. */
export function fallbackReasonText(code: string | null | undefined, label?: string | null): string | null {
  if (label && label.trim()) return label.trim();
  if (!code) return null;
  const known = FALLBACK_REASONS[code];
  if (known) return known;
  const words = humanizeCode(code);
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/* ------------------------------------------------------------------ */
/* Occupancy sources                                                   */
/* ------------------------------------------------------------------ */

export type SourceMeta = { label: string; tone: StatusTone; trains: boolean };

const SOURCE_META: Record<string, SourceMeta> = {
  imported: { label: "Imported", tone: "sky", trains: true },
  demo: { label: "Demo", tone: "violet", trains: true },
  manual: { label: "Manual", tone: "indigo", trains: true },
  generated: { label: "App-generated — not used for training", tone: "slate", trains: false },
};

/** Fixed label for each occupancy row source. Generated rows never train the model. */
export function sourceMeta(source: OccupancySource | null | undefined): SourceMeta | null {
  if (!source) return null;
  const known = SOURCE_META[String(source).toLowerCase()];
  if (known) return known;
  const words = humanizeCode(String(source));
  return { label: words.charAt(0).toUpperCase() + words.slice(1), tone: "slate", trains: true };
}

export function sourceLabel(source: OccupancySource | null | undefined): string {
  return sourceMeta(source)?.label ?? EMPTY;
}

/* ------------------------------------------------------------------ */
/* "Why this price?" inputs                                            */
/* ------------------------------------------------------------------ */

export type InputLine = { label: string; value: string };

/** The request behind a quote, in plain words. */
export function describeInputs(inputs: Partial<QuoteExplanationInputs> | null | undefined): InputLine[] {
  if (!inputs) return [];
  // Quotes made before explanations were stored come back with `inputs: {}`.
  const known = [inputs.base_price, inputs.room_nights, inputs.space_name, inputs.nights, inputs.check_in];
  if (known.every((v) => v === null || v === undefined || v === "")) return [];
  const lines: InputLine[] = [];
  const roomNights = num(inputs.room_nights);
  if (roomNights !== null && roomNights > 0) {
    const peak = num(inputs.peak_rooms_per_night);
    lines.push({
      label: "Guest rooms",
      value:
        `${formatCount(roomNights)} room ${roomNights === 1 ? "night" : "nights"} × ${formatMoney(inputs.room_rate)}` +
        ` = ${formatMoney(inputs.rooms_part)}` +
        (peak !== null && peak > 0 ? ` (up to ${formatCount(peak)} rooms a night)` : ""),
    });
  } else {
    lines.push({ label: "Guest rooms", value: "None — meeting space only" });
  }

  const days = num(inputs.event_days);
  if (inputs.space_name) {
    lines.push({
      label: "Meeting space",
      value:
        `${inputs.space_name}` +
        (days !== null ? ` × ${formatCount(days)} ${days === 1 ? "day" : "days"}` : "") +
        ` × ${formatMoney(inputs.space_rate)} = ${formatMoney(inputs.space_part)}`,
    });
  } else {
    lines.push({ label: "Meeting space", value: "None" });
  }

  lines.push({ label: "Base price", value: `${formatMoney(inputs.base_price)} (rooms plus space)` });

  const nights = num(inputs.nights);
  const nightsText = nights !== null ? `${formatCount(nights)} ${nights === 1 ? "night" : "nights"}` : null;
  if (inputs.check_in) {
    const dates = inputs.check_out
      ? `${formatDate(inputs.check_in)} to ${formatDate(inputs.check_out)}`
      : `from ${formatDate(inputs.check_in)}`;
    lines.push({ label: "Stay", value: nightsText ? `${nightsText}, ${dates}` : dates });
  } else {
    lines.push({ label: "Stay", value: nightsText ? `${nightsText}, dates not set` : "Dates not set" });
  }
  return lines;
}

/* ------------------------------------------------------------------ */
/* Waterfall (plan §3 D3)                                              */
/* ------------------------------------------------------------------ */

export const ENDS_LABEL = { target: "Goal price", anchor: "Opening offer" } as const;

export type WaterfallDirection = "base" | "up" | "down" | "flat" | "total";

export type WaterfallRow = {
  /** Unique within the chart (React key). */
  id: string;
  key: string;
  label: string;
  kind: string;
  direction: WaterfallDirection;
  /** Signed change for a step; the full value for base and total rows. */
  amount: number;
  /** Price before this row (0 for totals). */
  start: number;
  /** Price after this row. */
  end: number;
  /** Bar position on the shared 0 → max scale, in percent. leftPct + widthPct ≤ 100. */
  leftPct: number;
  widthPct: number;
  ends: "target" | "anchor" | null;
  isTotal: boolean;
};

export type Waterfall = {
  rows: WaterfallRow[];
  /** Right edge of the scale (the largest running total). */
  max: number;
  /** Gridline spacing in money, and the tick values from 0 up to `max`. */
  tickStep: number;
  ticks: number[];
};

type StepInput = Pick<QuoteExplanationStep, "label" | "kind" | "amount" | "running_total"> & {
  key?: string | null;
  ends?: QuoteExplanationStep["ends"] | null;
};

const clampPct = (v: number) => Math.min(100, Math.max(0, v));

/** A "nice" gridline step (1, 2, 2.5 or 5 × 10ⁿ) giving about `count` intervals up to `max`. */
export function niceStep(max: number, count = 4): number {
  if (!Number.isFinite(max) || max <= 0) return 1;
  const raw = max / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10]) {
    if (m * mag >= raw - 1e-9) return m * mag;
  }
  return 10 * mag;
}

/**
 * Lays the waterfall out on one linear scale from 0 to the largest running total.
 * Each step's bar runs from the previous running total to its own; a neutral total
 * row ("Goal price" / "Opening offer") follows each step that ends at the target or anchor.
 */
export function buildWaterfall(
  steps: StepInput[] | null | undefined,
  opts: { totals?: boolean; tickCount?: number } = {},
): Waterfall {
  const withTotals = opts.totals ?? true;
  type Draft = Omit<WaterfallRow, "leftPct" | "widthPct">;
  const drafts: Draft[] = [];
  let prev = 0;

  (steps ?? []).forEach((s, i) => {
    const key = s.key || `step-${i}`;
    const amountRaw = num(s.amount);
    const start = prev;
    const end = num(s.running_total) ?? start + (amountRaw ?? 0);
    const amount = amountRaw ?? end - start;
    const isBase = s.kind === "base";
    const delta = amount !== 0 ? amount : end - start;
    const direction: WaterfallDirection = isBase ? "base" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
    const ends = s.ends === "target" || s.ends === "anchor" ? s.ends : null;
    drafts.push({
      id: `${i}:${key}`,
      key,
      label: s.label || "Step",
      kind: String(s.kind || "step"),
      direction,
      amount,
      start,
      end,
      ends,
      isTotal: false,
    });
    if (withTotals && ends) {
      drafts.push({
        id: `${i}:${key}:total`,
        key: `${key}:total`,
        label: ENDS_LABEL[ends],
        kind: "total",
        direction: "total",
        amount: end,
        start: 0,
        end,
        ends,
        isTotal: true,
      });
    }
    prev = end;
  });

  const max = drafts.reduce((m, d) => Math.max(m, d.start, d.end), 0);
  const scale = max > 0 ? max : 1;
  const rows = drafts.map((d) => {
    const lo = clampPct((Math.min(d.start, d.end) / scale) * 100);
    const hi = clampPct((Math.max(d.start, d.end) / scale) * 100);
    return { ...d, leftPct: lo, widthPct: Math.max(0, hi - lo) };
  });

  const tickStep = niceStep(max, opts.tickCount ?? 4);
  const ticks: number[] = [];
  if (max > 0) {
    for (let t = 0; t <= max + tickStep * 1e-9; t += tickStep) ticks.push(Math.round(t * 1e6) / 1e6);
  }
  return { rows, max, tickStep, ticks };
}

/** Where a value sits on the waterfall scale, 0–100. */
export function scalePct(value: number, max: number): number {
  return max > 0 ? clampPct((value / max) * 100) : 0;
}

/** "+4,000", "−1,200" (true minus sign), "0". */
export function formatSignedMoney(value: number | string | null | undefined): string {
  const n = num(value);
  if (n === null) return EMPTY;
  const text = formatMoney(Math.abs(n));
  if (text === "0") return "0";
  return n > 0 ? `+${text}` : `−${text}`;
}

/**
 * True when the waterfall's goal / opening-offer totals don't match the saved prices
 * (more than 1 unit apart), so the page can say so instead of showing a wrong picture.
 */
export function waterfallMismatch(
  wf: Waterfall,
  prices: { target?: Money | null; anchor?: Money | null },
): boolean {
  for (const which of ["target", "anchor"] as const) {
    const expected = num(prices[which]);
    const row = [...wf.rows].reverse().find((r) => r.ends === which && !r.isTotal);
    if (expected === null || !row) continue;
    if (Math.abs(row.end - expected) > 1) return true;
  }
  return false;
}
