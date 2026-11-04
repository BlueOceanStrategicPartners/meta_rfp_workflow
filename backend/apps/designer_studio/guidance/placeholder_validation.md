## Placeholder validation checklist

Binding **data shapes** (arrays, columns, lists): see **`proposal_binding_schema.md`** — validate template wiring matches JSON bindings, not inline HTML row data.

Use this when reviewing **compiled** preview HTML **and** source `html_markup` with `{{tokens}}`.

### Must pass (blockers)

- Every mandatory token present **exactly once** in source HTML: {{MANDATORY_PLACEHOLDERS_LIST}}.
- Accept CTA visible at desktop: `{{cta_accept_button}}` or `.proposal-cta` not hidden via `display:none`.
- No hardcoded guest-visible ISO dates (`YYYY-MM-DD`) when the user requested U.S. formatting — dates should flow from `{{event_dates}}` / `{{verified_room_blocks}}` only.
- **No hardcoded sample data for any mandatory binding** in saved `html_markup`: not literal marketing date ranges, block KPIs (rooms/night, nights, room-nights), package prices, or client company names on `[data-proposal-field="…"]` or `.room-block-*` — use neutral placeholders; runtime/compile fills live RFP data (see proposal_binding_schema.md).
- Room-block sections: dynamic numbers and row content must not contradict the binding model (no full static pricing table **without** `{{verified_room_blocks}}` in the dynamic region).

### Room block / table-specific

- Templates must use **JSON bindings** + `data-proposal-bind="verified_room_blocks"` — not server-injected `<tr>` HTML.
- Flag templates that expect pre-rendered HTML tables inside `{{verified_room_blocks}}`.

### Pricing placeholder

- `{{xgboost_quote_breakdown}}` is for **package-level** floor / target / anchor (and similar), not per-row XGBoost cells.
- Flag designs that imply every table rate cell is ML-filled when only the breakdown token is bound today.

### Do not flag (false positives)

- Raw `{{binding_tokens}}` in **source** `html_markup` — required; not "unresolved".
- Sample table HTML in **compiled preview** replacing `{{verified_room_blocks}}` — expected in Designer.
- **Compiled** guest-visible copy showing raw `{` JSON — defect; bindings belong in JSON scripts with display text or `[data-proposal-field]` hydration.
- Optional venue map section omitted when the user removed the map.
- Prompt truncation of CSS/JS in the validation message — not a template defect.

### Summary line for model

If placeholders are present once, CTA is visible, and room-block layout defers live numbers to `{{verified_room_blocks}}`, prefer **valid** unless layout, XSS, or JS safety issues remain.
