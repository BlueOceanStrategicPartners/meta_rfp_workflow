import { describe, expect, it } from "vitest";
import type { PricingModelStatus, QuoteExplanationStep } from "./adminApi";
import {
  ENDS_LABEL,
  buildWaterfall,
  describeInputs,
  engineLabel,
  fallbackReasonText,
  formatMonthRange,
  formatPlainPct,
  formatSignedMoney,
  modelQuality,
  metricPct,
  modelStatusSummary,
  niceStep,
  retrainFeedback,
  sourceLabel,
  sourceMeta,
  topFactors,
  trainingDataLine,
  waterfallMismatch,
} from "./adminPricing";

/** The plan §4 worked example on the model engine: base 61,200 → target 79,438 → anchor 85,793. */
const STEPS: QuoteExplanationStep[] = [
  { key: "base", label: "Base price", kind: "base", amount: "61200.00", running_total: "61200.00", ends: null },
  { key: "normal", label: "Normal demand", kind: "demand", amount: "3060.00", running_total: "64260.00", ends: null },
  { key: "dec", label: "December demand +10%", kind: "demand", amount: "6120.00", running_total: "70380.00", ends: null },
  { key: "tue", label: "Tuesday nights −5%", kind: "demand", amount: "-3060.00", running_total: "67320.00", ends: null },
  { key: "goal", label: "Goal markup", kind: "markup", amount: "12117.60", running_total: "79437.60", ends: "target" },
  { key: "offer", label: "Opening-offer markup", kind: "markup", amount: "6355.01", running_total: "85792.61", ends: "anchor" },
];

const BASE_MODEL: PricingModelStatus = {
  artifact_exists: true,
  trained_at: "2026-11-05T10:00:00Z",
  occupancy_rows: 1095,
  min_rows_required: 60,
  version: 3,
  is_active: true,
  inactive_reason: null,
  rows_used: 1095,
  date_from: "2023-11-01",
  date_to: "2026-10-31",
  // As the training code writes them: percents already ×100.
  metrics: { mae: 0.04, mape: 4.12, baseline_mae: 0.052, improvement_pct: 23.4 },
  feature_importance: [],
  data: { imported: 1095, demo: 0, manual: 0, generated: 120, trainable: 1095 },
  last_error: null,
};

describe("waterfall scale", () => {
  const wf = buildWaterfall(STEPS);

  it("puts every bar inside 0–100% of one shared scale", () => {
    expect(wf.max).toBeCloseTo(85792.61, 2);
    for (const r of wf.rows) {
      expect(r.leftPct).toBeGreaterThanOrEqual(0);
      expect(r.widthPct).toBeGreaterThanOrEqual(0);
      expect(r.leftPct + r.widthPct).toBeLessThanOrEqual(100 + 1e-9);
    }
  });

  it("draws each step from the previous running total to its own, to scale", () => {
    const pct = (v: number) => (v / 85792.61) * 100;
    const base = wf.rows[0];
    expect(base.direction).toBe("base");
    expect(base.leftPct).toBe(0);
    expect(base.widthPct).toBeCloseTo(pct(61200), 6);

    const dec = wf.rows.find((r) => r.key === "dec")!;
    expect(dec.direction).toBe("up");
    expect(dec.start).toBeCloseTo(64260, 2);
    expect(dec.leftPct).toBeCloseTo(pct(64260), 6);
    expect(dec.widthPct).toBeCloseTo(pct(6120), 6);
  });

  it("draws negative steps leftwards from the previous total", () => {
    const tue = wf.rows.find((r) => r.key === "tue")!;
    expect(tue.direction).toBe("down");
    expect(tue.amount).toBe(-3060);
    expect(tue.start).toBeCloseTo(70380, 2);
    expect(tue.end).toBeCloseTo(67320, 2);
    // The bar spans 67,320 → 70,380: it starts at the new (lower) total.
    expect(tue.leftPct).toBeCloseTo((67320 / 85792.61) * 100, 6);
    expect(tue.widthPct).toBeCloseTo((3060 / 85792.61) * 100, 6);
  });

  it("adds Goal price and Opening offer totals that match the running totals", () => {
    const totals = wf.rows.filter((r) => r.isTotal);
    expect(totals.map((r) => r.label)).toEqual([ENDS_LABEL.target, ENDS_LABEL.anchor]);
    expect(totals.map((r) => r.direction)).toEqual(["total", "total"]);
    expect(totals[0].end).toBeCloseTo(79437.6, 2);
    expect(totals[0].leftPct).toBe(0);
    expect(totals[1].widthPct).toBeCloseTo(100, 9);
    // Each total sits right after the step that ends there.
    const goalIdx = wf.rows.findIndex((r) => r.key === "goal");
    expect(wf.rows[goalIdx + 1]).toBe(totals[0]);
    // Steps add up: base + every change = the anchor.
    const sum = wf.rows.filter((r) => !r.isTotal).reduce((s, r) => s + r.amount, 0);
    expect(sum).toBeCloseTo(85792.61, 2);
    expect(waterfallMismatch(wf, { target: "79437.60", anchor: "85792.61" })).toBe(false);
    expect(waterfallMismatch(wf, { target: "90000.00", anchor: "85792.61" })).toBe(true);
  });

  it("can leave the totals out", () => {
    expect(buildWaterfall(STEPS, { totals: false }).rows).toHaveLength(STEPS.length);
  });

  it("clamps a running total below zero and copes with empty input", () => {
    const weird = buildWaterfall([
      { key: "b", label: "Base", kind: "base", amount: 100, running_total: 100, ends: null },
      { key: "x", label: "Huge discount", kind: "rule", amount: -150, running_total: -50, ends: null },
    ]);
    for (const r of weird.rows) {
      expect(r.leftPct).toBeGreaterThanOrEqual(0);
      expect(r.leftPct + r.widthPct).toBeLessThanOrEqual(100);
    }
    expect(weird.rows[1].leftPct).toBe(0);
    expect(weird.rows[1].widthPct).toBeCloseTo(100, 9);

    const none = buildWaterfall([]);
    expect(none.rows).toEqual([]);
    expect(none.ticks).toEqual([]);
  });

  it("uses running_total when a step's amount is missing", () => {
    const wf2 = buildWaterfall([
      { key: "b", label: "Base", kind: "base", amount: "1000", running_total: "1000", ends: null },
      { key: "g", label: "Guard", kind: "guard", amount: "", running_total: "1200", ends: "target" },
    ]);
    expect(wf2.rows[1].amount).toBe(200);
    expect(wf2.rows[1].direction).toBe("up");
  });

  it("picks nice gridlines that never pass the scale end", () => {
    expect(niceStep(85792.61, 4)).toBe(25000);
    expect(wf.ticks).toEqual([0, 25000, 50000, 75000]);
    expect(niceStep(100, 4)).toBe(25);
    expect(niceStep(0)).toBe(1);
  });

  it("formats signed amounts with a real minus sign", () => {
    expect(formatSignedMoney(4000)).toBe("+4,000");
    expect(formatSignedMoney("-1200.4")).toBe("−1,200");
    expect(formatSignedMoney(0)).toBe("0");
    expect(formatSignedMoney(null)).toBe("—");
  });
});

describe("model status sentence", () => {
  it("describes a trained, active model with days and months", () => {
    const s = modelStatusSummary(BASE_MODEL);
    expect(s.state).toBe("active");
    expect(s.headline).toBe("Trained on 1,095 days (Nov 2023 – Oct 2026).");
    expect(s.chip).toEqual({ label: "In use", tone: "green" });
    expect(s.detail).toMatch(/^Version 3 · trained /);
  });

  it("says when there is no model yet", () => {
    const s = modelStatusSummary({
      artifact_exists: false,
      trained_at: null,
      occupancy_rows: 10,
      min_rows_required: 60,
    });
    expect(s.state).toBe("none");
    expect(s.headline).toBe("Not trained yet — quotes use the simple formula.");
  });

  it("explains an inactive model that isn't better than the baseline", () => {
    const s = modelStatusSummary({
      ...BASE_MODEL,
      is_active: false,
      inactive_reason: "model_not_better_than_baseline",
    });
    expect(s.state).toBe("inactive");
    expect(s.headline).toBe("Trained, but not better than a simple average — still using the simple formula.");
    expect(s.chip.tone).toBe("amber");
  });

  it("handles an inactive model with no reason", () => {
    const notBetter = modelStatusSummary({
      ...BASE_MODEL,
      is_active: false,
      inactive_reason: "",
      metrics: { mae: 0.06, mape: 6, baseline_mae: 0.05, improvement_pct: -3 },
    });
    expect(notBetter.headline).toMatch(/^Trained, but not better than a simple average/);
    const unknown = modelStatusSummary({ ...BASE_MODEL, is_active: false, inactive_reason: "", metrics: null });
    expect(unknown.headline).toMatch(/^Trained, but not in use yet/);
  });

  it("passes other inactive reasons through in plain words", () => {
    expect(modelStatusSummary({ ...BASE_MODEL, is_active: false, inactive_reason: "feature_mismatch" }).headline).toBe(
      "Trained, but not in use (feature mismatch) — still using the simple formula.",
    );
    expect(
      modelStatusSummary({ ...BASE_MODEL, is_active: false, inactive_reason: "Model file is damaged." }).headline,
    ).toBe("Trained, but not in use (Model file is damaged) — still using the simple formula.");
  });

  it("works with an older backend that has none of the new fields", () => {
    const s = modelStatusSummary({
      artifact_exists: true,
      trained_at: "2026-11-01T10:00:00Z",
      occupancy_rows: 400,
      min_rows_required: 60,
    });
    expect(s.state).toBe("active");
    expect(s.headline).toBe("Trained and in use.");
  });

  it("formats month ranges", () => {
    expect(formatMonthRange("2023-11-01", "2026-10-31")).toBe("Nov 2023 – Oct 2026");
    expect(formatMonthRange("2026-10-01", "2026-10-31")).toBe("Oct 2026");
    expect(formatMonthRange(null, null)).toBe("");
  });
});

describe("model quality and factors", () => {
  it("reads metrics as percent numbers and never rescales them", () => {
    expect(metricPct(23.4)).toBe(23.4);
    expect(metricPct("0.5")).toBe(0.5); // 0.5% better, not 50%
    expect(metricPct(null)).toBeNull();
    expect(modelQuality({ mae: 0.05, mape: 0.8, baseline_mae: 0.05, improvement_pct: 0.5 })).toEqual({
      error: "Typical error ±0.8%",
      improvement: "0.5% better than a simple average",
      better: true,
    });
    expect(formatPlainPct(4.12)).toBe("4.1%");
    expect(formatPlainPct(23.4)).toBe("23%");
    expect(formatPlainPct(4)).toBe("4%");
  });

  it("puts quality in plain words", () => {
    expect(modelQuality(BASE_MODEL.metrics)).toEqual({
      error: "Typical error ±4.1%",
      improvement: "23% better than a simple average",
      better: true,
    });
    expect(modelQuality({ mae: 0.1, mape: 12, baseline_mae: 0.09, improvement_pct: -10 })?.improvement).toBe(
      "Not better than a simple average",
    );
    expect(modelQuality(null)).toBeNull();
    expect(modelQuality({ mae: null, mape: null, baseline_mae: null, improvement_pct: null })).toBeNull();
  });

  it("keeps the top five factors, biggest first, scaled to the top one", () => {
    const bars = topFactors([
      { feature: "dow_sin", label: "Day of the week", importance: 0.1 },
      { feature: "same_week_occ", label: "Same week in past years", importance: 0.4 },
      { feature: "month_sin", label: "Time of year", importance: 0.2 },
      { feature: "is_peak", label: "Peak season", importance: 0.15 },
      { feature: "event", label: "City events", importance: 0.1 },
      { feature: "week", label: "Week of the year", importance: 0.05 },
      { feature: "zero", label: "Unused", importance: 0 },
    ]);
    expect(bars.map((b) => b.label)).toEqual([
      "Same week in past years",
      "Time of year",
      "Peak season",
      "Day of the week",
      "City events",
    ]);
    expect(bars[0].widthPct).toBe(100);
    expect(bars[1].widthPct).toBeCloseTo(50);
    expect(bars[0].share).toBeCloseTo(0.4);
  });

  it("turns raw importances into shares", () => {
    const bars = topFactors([
      { feature: "a", label: "", importance: 30 },
      { feature: "b_c", label: "B", importance: 10 },
    ]);
    expect(bars[0].label).toBe("A");
    expect(bars[0].share).toBeCloseTo(0.75);
    expect(topFactors(null)).toEqual([]);
  });

  it("summarises the training data", () => {
    expect(trainingDataLine(BASE_MODEL.data)).toBe("1,095 days used for training · 120 app-generated days ignored");
    expect(trainingDataLine({ imported: 1, demo: 0, manual: 0, generated: 0, trainable: 1 })).toBe(
      "1 day used for training",
    );
    expect(trainingDataLine(null)).toBeNull();
  });
});

describe("retrain feedback", () => {
  const base = { trained_at: null };
  it("has one message per status", () => {
    expect(retrainFeedback({ ...base, status: "ok" })).toEqual({
      message: "Model retrained. New quotes use it.",
      tone: "success",
    });
    expect(retrainFeedback({ ...base, status: "skipped_insufficient_data", rows_available: 12, rows_required: 60 })).toEqual({
      message: "Not enough history: 12 of 60 days. Import more on the Occupancy page.",
      tone: "warning",
    });
    expect(retrainFeedback({ ...base, status: "inactive_not_better" }).message).toMatch(/simple formula/);
    expect(retrainFeedback({ ...base, status: "error", detail: "Model file is damaged." })).toEqual({
      message: "Model file is damaged.",
      tone: "error",
    });
    expect(retrainFeedback({ ...base, status: "error" }).message).toMatch(/Retraining failed/);
  });
});

describe("engine and source labels", () => {
  it("labels the engine", () => {
    expect(engineLabel({ engine: "model", model_version: 3 })).toBe("Model v3");
    expect(engineLabel({ engine: "model", model_version: "v4" })).toBe("Model v4");
    expect(engineLabel({ engine: "model", model_version: null })).toBe("Model");
    expect(engineLabel({ engine: "fallback", model_version: 3 })).toBe("Simple formula");
    // Older rows without `engine`.
    expect(engineLabel({ used_fallback: false })).toBe("Model");
    expect(engineLabel({ used_fallback: true })).toBe("Simple formula");
  });

  it("explains fallback reasons, preferring the backend's label", () => {
    expect(fallbackReasonText("no_model", "No model has been trained")).toBe("No model has been trained");
    expect(fallbackReasonText("no_model")).toBe("No model trained yet");
    expect(fallbackReasonText("something_new")).toBe("Something new");
    expect(fallbackReasonText(null)).toBeNull();
  });

  it("labels every occupancy source", () => {
    expect(sourceLabel("imported")).toBe("Imported");
    expect(sourceLabel("demo")).toBe("Demo");
    expect(sourceLabel("manual")).toBe("Manual");
    expect(sourceLabel("generated")).toBe("App-generated — not used for training");
    expect(sourceMeta("generated")?.trains).toBe(false);
    expect(sourceMeta("imported")?.trains).toBe(true);
    expect(sourceLabel("csv_sync")).toBe("Csv sync");
    expect(sourceLabel(null)).toBe("—");
  });
});

describe("inputs summary", () => {
  it("describes the request in plain words", () => {
    const lines = describeInputs({
      check_in: "2026-12-01",
      check_out: "2026-12-04",
      nights: 3,
      dates_assumed: false,
      room_nights: 180,
      peak_rooms_per_night: 60,
      room_rate: "220.00",
      rooms_part: "39600.00",
      space_id: "s1",
      space_name: "Lotus Pavilion",
      event_days: 3,
      space_rate: "7200.00",
      space_part: "21600.00",
      base_price: "61200.00",
      operating_cost: "37380.00",
      warnings: [],
    });
    expect(lines).toEqual([
      { label: "Guest rooms", value: "180 room nights × 220 = 39,600 (up to 60 rooms a night)" },
      { label: "Meeting space", value: "Lotus Pavilion × 3 days × 7,200 = 21,600" },
      { label: "Base price", value: "61,200 (rooms plus space)" },
      { label: "Stay", value: "3 nights, Dec 1, 2026 to Dec 4, 2026" },
    ]);
  });

  it("handles a meeting-only request without dates", () => {
    const lines = describeInputs({
      check_in: null,
      check_out: null,
      nights: 1,
      dates_assumed: true,
      room_nights: 0,
      peak_rooms_per_night: 0,
      room_rate: null,
      rooms_part: "0",
      space_id: null,
      space_name: null,
      event_days: null,
      space_rate: null,
      space_part: null,
      base_price: "5000",
      operating_cost: null,
      warnings: [],
    });
    expect(lines[0].value).toBe("None — meeting space only");
    expect(lines[1].value).toBe("None");
    expect(lines[3].value).toBe("1 night, dates not set");
  });

  it("returns nothing for an old quote saved without inputs", () => {
    expect(describeInputs({})).toEqual([]);
    expect(describeInputs(null)).toEqual([]);
  });
});
