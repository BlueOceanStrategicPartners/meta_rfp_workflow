import { describe, expect, it } from "vitest";
import { parseProposalPostMessage } from "./proposalClientBridge";

describe("parseProposalPostMessage", () => {
  it("parses rfp-proposal-event mutations", () => {
    const out = parseProposalPostMessage({
      type: "rfp-proposal-event",
      kind: "mutation",
      action: "field_change",
      label: "Updated room_block.peak_rooms",
      cardPatch: { room_block: { peak_rooms: 12 } },
    });
    expect(out?.kind).toBe("mutation");
    expect(out?.cardPatch).toEqual({ room_block: { peak_rooms: 12 } });
  });

  it("parses venue-map-select as awareness event", () => {
    const out = parseProposalPostMessage({
      type: "venue-map-select",
      locationId: "zone-a",
      label: "Grand Ballroom",
    });
    expect(out?.action).toBe("map_select");
    expect(out?.meta?.locationId).toBe("zone-a");
  });

  it("ignores unrelated messages", () => {
    expect(parseProposalPostMessage({ type: "other" })).toBeNull();
  });
});
