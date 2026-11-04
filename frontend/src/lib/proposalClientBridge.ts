export type ProposalInteractionPayload = {
  kind: "event" | "mutation";
  action: string;
  label: string;
  cardPatch?: Record<string, unknown> | null;
  meta?: Record<string, unknown>;
};

type RawPostMessage = {
  type?: string;
  kind?: string;
  action?: string;
  label?: string;
  cardPatch?: Record<string, unknown> | null;
  card_patch?: Record<string, unknown> | null;
  meta?: Record<string, unknown>;
  locationId?: string;
  description?: string;
};

/** Normalize iframe postMessage into a proposal interaction payload. */
export function parseProposalPostMessage(data: unknown): ProposalInteractionPayload | null {
  if (!data || typeof data !== "object") return null;
  const raw = data as RawPostMessage;
  if (raw.type === "venue-map-select") {
    return {
      kind: "event",
      action: "map_select",
      label: String(raw.label || raw.locationId || "Selected venue on map"),
      meta: {
        locationId: raw.locationId,
        description: (raw as { description?: string }).description,
      },
    };
  }
  if (raw.type !== "rfp-proposal-event") return null;
  const kind = raw.kind === "mutation" ? "mutation" : "event";
  return {
    kind,
    action: String(raw.action || "interaction"),
    label: String(raw.label || raw.action || "Proposal interaction"),
    cardPatch: raw.cardPatch ?? raw.card_patch ?? null,
    meta: raw.meta,
  };
}
