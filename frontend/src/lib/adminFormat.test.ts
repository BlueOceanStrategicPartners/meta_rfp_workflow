import { describe, expect, it } from "vitest";
import {
  EMPTY,
  RFP_STATUSES,
  actionLabel,
  collectQuotes,
  computeLadderExample,
  formatDate,
  formatDuration,
  formatMoney,
  formatMs,
  formatPct,
  formatRelativeTime,
  highlightSegments,
  overCapacityMessage,
  seasonFor,
  shortId,
  statusMeta,
  validatePolicy,
  type PolicyNumbers,
} from "./adminFormat";

const DEFAULT_POLICY: PolicyNumbers = {
  walk_away_floor_margin_pct: 0.12,
  max_autonomous_discount_pct: 0.15,
  target_markup_pct: 0.18,
  anchor_markup_pct: 0.08,
  event_multiplier: 1,
  seasonality_json: { "6": 1.15, "7": 1.15, "11": 1.15, "12": 1.15 },
};

describe("statusMeta", () => {
  it("has a fixed label and tone for every RFP status", () => {
    const expected: Record<string, [string, string]> = {
      EXTRACTING: ["In debate", "violet"],
      DEBATING: ["In debate", "violet"],
      AWAITING_USER_CARD_EDIT: ["Awaiting client", "sky"],
      PRICING: ["Negotiating", "emerald"],
      NEGOTIATING: ["Negotiating", "emerald"],
      PROPOSAL_RENDERED: ["Proposal sent", "indigo"],
      BOOKED: ["Booked", "green"],
      ESCALATED: ["Human takeover", "amber"],
    };
    expect(RFP_STATUSES).toHaveLength(8);
    for (const s of RFP_STATUSES) {
      const meta = statusMeta(s);
      expect([meta.label, meta.tone]).toEqual(expected[s]);
      expect(meta.step.length).toBeGreaterThan(0);
    }
  });

  it("gives every status a distinct funnel step name", () => {
    const steps = RFP_STATUSES.map((s) => statusMeta(s).step);
    expect(new Set(steps).size).toBe(steps.length);
  });

  it("falls back to a readable label for unknown statuses", () => {
    expect(statusMeta("SOMETHING_NEW")).toEqual({ label: "Something new", step: "Something new", tone: "slate" });
    expect(statusMeta(null).tone).toBe("slate");
    expect(statusMeta("booked").label).toBe("Booked");
  });
});

describe("money and percentages", () => {
  it("formats money without a currency symbol or decimals", () => {
    expect(formatMoney("28560.00")).toBe("28,560");
    expect(formatMoney(32497.2)).toBe("32,497");
    expect(formatMoney("1234.5")).toBe("1,235");
    expect(formatMoney(null)).toBe(EMPTY);
    expect(formatMoney("")).toBe(EMPTY);
    expect(formatMoney("abc")).toBe(EMPTY);
  });

  it("formats fractions as percentages with one decimal", () => {
    expect(formatPct(0.12)).toBe("12.0%");
    expect(formatPct(1)).toBe("100.0%");
    expect(formatPct(0.0833)).toBe("8.3%");
    expect(formatPct("0.5")).toBe("50.0%");
    expect(formatPct(null)).toBe(EMPTY);
    expect(formatPct(undefined)).toBe(EMPTY);
  });
});

describe("durations and times", () => {
  it("formats seconds", () => {
    expect(formatDuration(13.94)).toBe("13.9 s");
    expect(formatDuration(0)).toBe("0.0 s");
    expect(formatDuration(120)).toBe("2 min");
    expect(formatDuration(125)).toBe("2 min 5 s");
    expect(formatDuration(3660)).toBe("1 h 1 min");
    expect(formatDuration(null)).toBe(EMPTY);
    expect(formatDuration(-3)).toBe(EMPTY);
  });

  it("formats milliseconds", () => {
    expect(formatMs(412)).toBe("412 ms");
    expect(formatMs(1500)).toBe("1.5 s");
    expect(formatMs(null)).toBe(EMPTY);
  });

  it("formats relative times", () => {
    const now = Date.parse("2026-11-03T12:00:00Z");
    expect(formatRelativeTime("2026-11-03T11:59:30Z", now)).toBe("just now");
    expect(formatRelativeTime("2026-11-03T11:55:00Z", now)).toBe("5 min ago");
    expect(formatRelativeTime("2026-11-03T09:00:00Z", now)).toBe("3 h ago");
    expect(formatRelativeTime("2026-11-01T12:00:00Z", now)).toBe("2 d ago");
    expect(formatRelativeTime(null, now)).toBe(EMPTY);
    expect(formatRelativeTime("not a date", now)).toBe(EMPTY);
  });

  it("reads bare dates as calendar days (no timezone shift)", () => {
    expect(formatDate("2026-12-01")).toBe("Dec 1, 2026");
    expect(formatDate(null)).toBe(EMPTY);
  });
});

describe("pricing ladder example", () => {
  it("matches the backend formula (3 nights in a hall at 8,500, floor cost 6,000)", () => {
    const ex = computeLadderExample(DEFAULT_POLICY, 8500, 3, 1, 6000);
    expect(Math.round(ex.floor)).toBe(20160); // 6,000 × 3 × 1.12
    expect(Math.round(ex.target)).toBe(30090); // 25,500 × 1.18
    expect(Math.floor(ex.anchor)).toBe(32497);
    expect(formatMoney(ex.floor)).toBe("20,160");
  });

  it("applies seasonality and the event multiplier to the price, not the floor", () => {
    const ex = computeLadderExample({ ...DEFAULT_POLICY, event_multiplier: 2 }, 1000, 1, 12, 500);
    expect(ex.base).toBeCloseTo(1000 * 1.15 * 2);
    expect(ex.floor).toBeCloseTo(500 * 1.12);
  });

  it("enforces floor < target < anchor even with a bad policy", () => {
    const ex = computeLadderExample(
      { ...DEFAULT_POLICY, walk_away_floor_margin_pct: 0.3, target_markup_pct: 0.1, anchor_markup_pct: 0 },
      1000,
      3,
      1,
      950,
    );
    expect(ex.target).toBeGreaterThanOrEqual(ex.floor * 1.05 - 1e-9);
    expect(ex.anchor).toBeGreaterThanOrEqual(ex.target * 1.03 - 1e-9);
  });

  it("treats missing months as 1.0", () => {
    expect(seasonFor(DEFAULT_POLICY.seasonality_json, 3)).toBe(1);
    expect(seasonFor(DEFAULT_POLICY.seasonality_json, 6)).toBe(1.15);
    expect(seasonFor(null, 6)).toBe(1);
  });
});

describe("validatePolicy", () => {
  it("accepts the default policy", () => {
    expect(validatePolicy(DEFAULT_POLICY)).toEqual({});
  });

  it("rejects a target markup at or below the floor margin", () => {
    const errors = validatePolicy({ ...DEFAULT_POLICY, target_markup_pct: 0.12 });
    expect(errors.target_markup_pct).toBeTruthy();
  });

  it("rejects out-of-range values", () => {
    const errors = validatePolicy({
      ...DEFAULT_POLICY,
      walk_away_floor_margin_pct: 1.5,
      max_autonomous_discount_pct: 0.6,
      anchor_markup_pct: 1.2,
      event_multiplier: 0.2,
      seasonality_json: { "1": 0.2, "2": 3.5 },
    });
    expect(errors.walk_away_floor_margin_pct).toBeTruthy();
    expect(errors.max_autonomous_discount_pct).toBeTruthy();
    expect(errors.anchor_markup_pct).toBeTruthy();
    expect(errors.event_multiplier).toBeTruthy();
    expect(errors.season_1).toBeTruthy();
    expect(errors.season_2).toBeTruthy();
    expect(errors.season_3).toBeUndefined();
  });

  it("rejects empty (NaN) inputs", () => {
    const errors = validatePolicy({ ...DEFAULT_POLICY, anchor_markup_pct: Number.NaN });
    expect(errors.anchor_markup_pct).toBeTruthy();
  });
});

describe("source highlighting", () => {
  it("collects verbatim quotes from nested extraction payloads", () => {
    const quotes = collectQuotes({
      company_name: { value: "Acme", source_citation: { page_number: 1, verbatim_quote: "Acme Corp" } },
      room_blocks: [{ nights: { value: 3, source_citation: { verbatim_quote: "three nights" } } }],
      headcount: { value: 200, source_citation: null },
    });
    expect([...quotes].sort()).toEqual(["Acme Corp", "three nights"]);
  });

  it("marks matches case-insensitively and merges overlaps", () => {
    const segs = highlightSegments("Hello ACME corp, three nights please", ["acme corp", "corp, three", "xx"]);
    expect(segs).toEqual([
      { text: "Hello ", mark: false },
      { text: "ACME corp, three", mark: true },
      { text: " nights please", mark: false },
    ]);
  });

  it("returns the whole text when nothing matches", () => {
    expect(highlightSegments("abc def", ["zzz"])).toEqual([{ text: "abc def", mark: false }]);
    expect(highlightSegments("", ["a"])).toEqual([]);
  });
});

describe("misc", () => {
  it("shortens ids", () => {
    expect(shortId("1234567890abcdef")).toBe("12345678");
    expect(shortId(null)).toBe(EMPTY);
  });

  it("labels audit actions in plain words", () => {
    expect(actionLabel("pricing.policy.update")).toBe("Updated pricing policy");
    expect(actionLabel("something.custom")).toBe("Something custom");
  });

  it("builds the over-capacity message", () => {
    expect(overCapacityMessage("Headcount 300 exceeds Ballroom capacity 250.", ["Hall A", "Hall B"])).toBe(
      "Headcount 300 exceeds Ballroom capacity 250. Try: Hall A, Hall B.",
    );
    expect(overCapacityMessage("Too many people.", [])).toBe("Too many people.");
  });
});
