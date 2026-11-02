/** Mandatory for save; map token optional when user removes the map section. */
export const OPTIONAL_PLACEHOLDERS = [] as const;

export const MANDATORY_PLACEHOLDERS = [
  "{{client_name}}",
  "{{event_dates}}",
  "{{verified_room_blocks}}",
  "{{meeting_space_specs}}",
  "{{xgboost_quote_breakdown}}",
  "{{negotiated_concessions}}",
  "{{cta_accept_button}}",
] as const;

/** @deprecated Use MANDATORY_PLACEHOLDERS — map is no longer required on save. */
export const REQUIRED_PLACEHOLDERS = MANDATORY_PLACEHOLDERS;

export const ALL_BINDING_PLACEHOLDERS = [
  ...MANDATORY_PLACEHOLDERS,
  ...OPTIONAL_PLACEHOLDERS,
] as const;

export { ROOM_BLOCK_LINE_ITEM_FIELDS, samplePreviewReplacements } from "./proposalBindingSamples";
