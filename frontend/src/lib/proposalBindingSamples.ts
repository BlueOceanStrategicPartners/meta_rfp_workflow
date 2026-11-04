import seed from "../data/proposal_binding_seed.json";

export type ProposalBindingSeed = typeof seed;

export type BindingPayloadMap = {
  client_name: { company_name: string };
  event_dates: (typeof seed)["event_dates"];
  verified_room_blocks: (typeof seed)["verified_room_blocks"];
  meeting_space_specs: (typeof seed)["meeting_space_specs"];
  xgboost_quote_breakdown: (typeof seed)["xgboost_quote_breakdown"];
  negotiated_concessions: (typeof seed)["negotiated_concessions"];
};

const BINDING_TOKEN_REGISTRY: Record<string, keyof BindingPayloadMap> = {
  "{{client_name}}": "client_name",
  "{{event_dates}}": "event_dates",
  "{{verified_room_blocks}}": "verified_room_blocks",
  "{{meeting_space_specs}}": "meeting_space_specs",
  "{{xgboost_quote_breakdown}}": "xgboost_quote_breakdown",
  "{{negotiated_concessions}}": "negotiated_concessions",
};

const JSON_SCRIPT_RE =
  /(<script\b[^>]*\btype\s*=\s*['"]application\/json['"][^>]*>)([\s\S]*?)(<\/script>)/gi;

function inferBindingStructureKind(data: unknown): string {
  if (!data || typeof data !== "object" || Array.isArray(data)) return "empty";
  const d = data as Record<string, unknown>;
  if (Array.isArray(d.line_items)) return "line_items_table";
  if (Array.isArray(d.items)) return "string_list";
  return Object.keys(d).length ? "object" : "empty";
}

function moneyDisplay(value: unknown): string {
  if (value == null || value === "") return "";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return n % 1 === 0 ? `$${n.toLocaleString("en-US")}` : `$${n.toFixed(2)}`;
}

export function formatBindingDisplay(
  payloadKey: keyof BindingPayloadMap,
  data: unknown,
): string {
  const kind = inferBindingStructureKind(data);
  if (payloadKey === "verified_room_blocks") return "";
  if (kind === "string_list" && data && typeof data === "object") {
    const items = (data as { items?: unknown[] }).items ?? [];
    return items.filter(Boolean).map(String).join(" · ");
  }
  if (payloadKey === "client_name" && data && typeof data === "object") {
    return String((data as { company_name?: string }).company_name ?? "");
  }
  if (payloadKey === "event_dates" && data && typeof data === "object") {
    const d = data as { display_range?: string; check_in?: string; check_out?: string };
    if (d.display_range) return d.display_range;
    return [d.check_in, d.check_out].filter(Boolean).join(" — ");
  }
  if (payloadKey === "meeting_space_specs" && data && typeof data === "object") {
    const d = data as {
      name?: string;
      seating_style?: string;
      headcount?: number;
      av?: string;
    };
    const bits: string[] = [];
    if (d.name) bits.push(d.name);
    if (d.seating_style) bits.push(d.seating_style);
    if (d.headcount) bits.push(`${d.headcount} guests`);
    if (d.av) bits.push(d.av);
    return bits.join(" · ");
  }
  if (payloadKey === "xgboost_quote_breakdown" && data && typeof data === "object") {
    const d = data as {
      walk_away_floor_price?: number;
      optimal_target_price?: number;
      initial_anchor_price?: number;
    };
    const parts: string[] = [];
    if (d.walk_away_floor_price != null) {
      parts.push(`Floor ${moneyDisplay(d.walk_away_floor_price)}`);
    }
    if (d.optimal_target_price != null) {
      parts.push(`Target ${moneyDisplay(d.optimal_target_price)}`);
    }
    if (d.initial_anchor_price != null) {
      parts.push(`Anchor ${moneyDisplay(d.initial_anchor_price)}`);
    }
    return parts.join(" · ");
  }
  return "";
}

function jsonForScriptTag(data: unknown): string {
  return JSON.stringify(data);
}

/** Mirrors backend substitute_bindings_in_html for Designer live preview. */
export function substituteBindingsInHtml(html: string, payloads: BindingPayloadMap): string {
  if (!html) return html;
  let out = html.replace(JSON_SCRIPT_RE, (_m, opening: string, inner: string, closing: string) => {
    let next = inner;
    for (const [token, key] of Object.entries(BINDING_TOKEN_REGISTRY)) {
      if (next.includes(token)) {
        next = next.split(token).join(jsonForScriptTag(payloads[key]));
      }
    }
    return opening + next + closing;
  });
  for (const [token, key] of Object.entries(BINDING_TOKEN_REGISTRY)) {
    const display = formatBindingDisplay(key, payloads[key]);
    out = out.split(token).join(display);
  }
  return out;
}

export function sampleBindingPayloads(): BindingPayloadMap {
  return {
    client_name: { company_name: seed.event_overview.company_name },
    event_dates: seed.event_dates,
    verified_room_blocks: seed.verified_room_blocks,
    meeting_space_specs: seed.meeting_space_specs,
    xgboost_quote_breakdown: seed.xgboost_quote_breakdown,
    negotiated_concessions: seed.negotiated_concessions,
  };
}

/** Designer preview with sample toggle off — empty bindings like client before cards exist. */
export function emptyBindingPayloads(): BindingPayloadMap {
  return {
    client_name: { company_name: "" },
    event_dates: {
      check_in: "",
      check_out: "",
      display_range: "",
      nights: 0,
    },
    verified_room_blocks: {
      schema_version: 1,
      line_items: [],
      summary: {},
      blocks: [],
    },
    meeting_space_specs: {
      name: "",
      seating_style: null,
      headcount: null,
      av: null,
    },
    xgboost_quote_breakdown: {},
    negotiated_concessions: { items: [] },
  };
}

/** JSON text for {{verified_room_blocks}} inside script#binding-verified-room-blocks */
export function sampleVerifiedRoomBlocksJson(): string {
  return JSON.stringify(seed.verified_room_blocks);
}

export function sampleBindingJson(key: keyof BindingPayloadMap): string {
  return JSON.stringify(sampleBindingPayloads()[key]);
}

export function samplePreviewReplacements(): Record<string, string> {
  const payloads = sampleBindingPayloads();
  const out: Record<string, string> = {};
  for (const [token, key] of Object.entries(BINDING_TOKEN_REGISTRY)) {
    out[token] = formatBindingDisplay(key, payloads[key]);
  }
  out["{{cta_accept_button}}"] =
    '<button type="button" class="proposal-cta">Accept Proposal</button>';
  return out;
}

const CTA_BUTTON_HTML =
  '<button type="button" class="proposal-cta">Accept Proposal</button>';

/** Compile preview with JSON in script tags and display text elsewhere. */
export function compileBindingsInTemplate(html: string, useSampleData = true): string {
  const payloads = useSampleData ? sampleBindingPayloads() : emptyBindingPayloads();
  return substituteBindingsInHtml(html, payloads).replace(
    "{{cta_accept_button}}",
    CTA_BUTTON_HTML,
  );
}

/** Column keys in line_items — for Designer UI hints */
export const ROOM_BLOCK_LINE_ITEM_FIELDS = [
  "category_name",
  "category_subtitle",
  "badge",
  "date_range",
  "nights",
  "quantity",
  "rate_per_night",
  "estimated_total",
] as const;
