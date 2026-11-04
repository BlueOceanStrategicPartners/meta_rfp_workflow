# Proposal binding schema (agent knowledge)

Compile/preview uses **context-aware substitution** (see `proposal_bindings.substitute_bindings_in_html`):

- **`{{token}}` inside `<script type="application/json">`** → replaced with **JSON** (machine-readable).
- **`{{token}}` in visible HTML** → replaced with **display text** via `format_binding_display` (never raw JSON in copy).

Seed reference: `backend/apps/designer_studio/samples/proposal_binding_seed.json`.

## Universal structure identification (auto-align when schema changes)

Inspect the **resolved JSON object** for each binding (after compile fills script tags). Do **not** hardcode field lists per product release — use this order:

| Detect | Kind | UI pattern |
|--------|------|------------|
| `line_items` is a non-empty **array** | `line_items_table` | Empty `<tbody data-proposal-bind="…">` + your `<thead>`; runtime or custom JS maps row object keys to cells |
| `items` is a **string array** | `string_list` | Bullets, chips, or `[data-proposal-field="…"]` with ` · `-joined display |
| Otherwise non-empty **object** | `object` | Scalar keys → labels/copy; use `[data-proposal-field="token_name"]` or your layout |
| Empty / missing | `empty` | Leave region blank; do not paste sample numbers in saved template |

**Registry:** `BINDING_TOKEN_REGISTRY` in `proposal_bindings.py` maps `{{placeholder}}` → payload key. New placeholders add one registry row + seed shape; identification rules above stay the same.

**Agent rule:** Prefer **one token in a JSON script** + **empty** `[data-proposal-field="…"]` for visible copy (runtime hydrates). Legacy templates may still put tokens in headings; compile will show display text, not JSON.

## Never hardcode placeholder data (saved template)

Binding placeholders exist so **live RFP card data** replaces seed at compile time. The design agent must **not** paste sample or marketing numbers into saved `html_markup` as if they were real guest data.

| Do not hardcode in visible HTML | Use instead |
|---------------------------------|-------------|
| Sample date ranges (`Nov 14 – 17, 2026`, `2026-06-01`) | `[data-proposal-field="event_dates"]` with neutral copy (`Your selected dates`, `—`) + `#binding-event-dates` JSON |
| Sample company names (`Acme Corp`) unless user asked for static demo copy | `[data-proposal-field="client_name"]` + `#binding-client-name` |
| Room/night KPIs (`120`, `3`, `360`) in `.room-block-rooms-per-night`, `.room-block-nights`, `.room-block-room-nights`, `#room-night-total` | Neutral `—` or `0` until runtime reads `verified_room_blocks.summary` |
| Per-category qty/rate/totals in static room **cards** or `<tr>` rows | Empty `<tbody data-proposal-bind="verified_room_blocks">` + runtime, **or** custom `js_script` that reads `#binding-verified-room-blocks` |
| Package prices in copy bound to `{{xgboost_quote_breakdown}}` | `[data-proposal-field="xgboost_quote_breakdown"]` or neutral “Pricing on request” until hydrate |

**Allowed:** Decorative capacity text unrelated to bindings (e.g. “Ballroom seats up to 500”) — but **never** use those numbers for the **client’s block** (rooms/night, nights, grand total).

**Designer preview** may show seed JSON after compile — that is not permission to save seed literals in HTML. Save-time checks flag hardcoded binding-driven numbers.

---

## Default behavior (always apply unless the user explicitly asks otherwise)

1. Treat every mandatory placeholder as a **JSON binding** going into  
   `<script type="application/json" id="…">{{token}}</script>`.
2. **Room block table** = **array of row objects** (`line_items`) + one **summary object** — you design `<thead>` and an **empty** `<tbody data-proposal-bind="verified_room_blocks">`; runtime fills rows.
3. **Lists** (e.g. concessions) = JSON **`items` array** — render with your own loop in `<script>` or use `[data-proposal-field]` text hydration.
4. Include **`proposal_binding_runtime.js`** once at the bottom of `html_markup` (or rely on compile injecting it in preview).
5. Include **`proposal_client_bridge.js`** once (or rely on compile injecting it for client render) so proposal clicks sync to the negotiation assistant.
6. Wire interactive controls with **`data-proposal-action`**, **`data-proposal-mutation="section.field"`**, or **`window.rfpProposalEmit({ kind, action, label, cardPatch })`** — mutations must use card keys (`event_overview`, `room_block`, `meeting_space`, `catering_av`).
7. Keep the **token literal** in source HTML exactly once; never replace tokens with sample JSON in the saved template.

## When the user explicitly overrides

| User says | You do |
|-----------|--------|
| "No runtime / my own script" | Still use JSON script nodes; implement custom JS that `JSON.parse` the same ids. |
| "Plain text dates only" | May use `[data-proposal-field="event_dates"]` + `#binding-event-dates` only; skip table bind. |
| "Static mock numbers in design" | Allowed only for **layout preview in chat**, not hardcoded in saved template for fields covered by bindings. |
| "Different columns" | Change `<thead>` labels; keep **`line_items` field names** below unless product changes the schema. |

If the user is silent, use the **default JSON + runtime** pattern below.

---

## Placeholder → JSON type → UI pattern

| Placeholder | JSON type | Script element `id` | How to show in proposal |
|-------------|-----------|---------------------|-------------------------|
| `{{client_name}}` | **object** `{ "company_name": string }` | `binding-client-name` | `[data-proposal-field="client_name"]` or your script |
| `{{event_dates}}` | **object** (dates + `display_range`, `nights`) | `binding-event-dates` | `[data-proposal-field="event_dates"]` |
| `{{verified_room_blocks}}` | **object** with **`line_items` array** + **`summary` object** | `binding-verified-room-blocks` | Empty `<tbody data-proposal-bind="verified_room_blocks">` + thead you design |
| `{{meeting_space_specs}}` | **object** (name, seating_style, headcount, av) | `binding-meeting-space` | Your section layout + optional script |
| `{{xgboost_quote_breakdown}}` | **object** (floor/target/anchor prices, currency) | `binding-xgboost-quote` | Pricing strip; map fields in your script |
| `{{negotiated_concessions}}` | **object** with **`items` string array** | `binding-negotiated-concessions` | `<ul>` via script or list markup you hydrate |
| `{{cta_accept_button}}` | **HTML string** (exception) | — | Insert token where accept control goes; class `proposal-cta` |

Mandatory list: {{MANDATORY_PLACEHOLDERS_LIST}}

---

## `verified_room_blocks` — array rows vs columns

**Array (rows):** `line_items[]` — one object per **table row** (room category line).

**Object (footer / KPIs):** `summary` — block totals, not repeated per row.

**Optional legacy array:** `blocks[]` — per-night `{ date, single, double, deluxe, suite }`; platform may derive `line_items` when line_items missing. Do not hand-author `blocks` in templates.

### Each `line_items[]` element (column binding)

| JSON field | Role in table | Typical column header |
|------------|---------------|------------------------|
| `category_name` | Primary label | Room category |
| `category_subtitle` | Secondary line | (subtext under category) |
| `badge` | Optional pill (e.g. MOST PICKED) | — |
| `date_range` | Stay span text | Dates |
| `nights` | number | Nights |
| `quantity` | Rooms/night or qty req. | Qty req. |
| `rate_per_night` | number (USD) | Rate / night |
| `estimated_total` | number (USD) | Est. total |

### `summary` object (not a row array)

| Field | Meaning |
|-------|---------|
| `rooms_per_night` | Total rooms per night across categories |
| `nights` | Block length |
| `room_nights` | rooms_per_night × nights |
| `avg_rate_per_night` | Blended avg |
| `grand_total` | Block total |
| `policy_notes` | Footnote string |

Runtime maps these fields to `.room-block-*` cells when using default `proposal_binding_runtime.js`.

---

## `negotiated_concessions` — list type

- Shape: `{ "items": [ "string", … ] }`
- **List** = `items` array — each entry is one bullet/concession line.
- Do not assume a single string unless you parse JSON yourself.

---

## `meeting_space_specs` — object (scalar fields)

Object keys: `name`, `seating_style`, `headcount`, `av` — display as structured copy, not a row array.

---

## `xgboost_quote_breakdown` — object (pricing tiers)

Object keys: `walk_away_floor_price`, `optimal_target_price`, `initial_anchor_price`, `currency` — package-level quote, not per `line_items` row.

---

## Greenfield scaffold checklist

When creating a new proposal template, include at minimum:

```html
<script type="application/json" id="binding-client-name">{{client_name}}</script>
<script type="application/json" id="binding-event-dates">{{event_dates}}</script>
<script type="application/json" id="binding-verified-room-blocks">{{verified_room_blocks}}</script>
<script type="application/json" id="binding-meeting-space">{{meeting_space_specs}}</script>
<script type="application/json" id="binding-xgboost-quote">{{xgboost_quote_breakdown}}</script>
<script type="application/json" id="binding-negotiated-concessions">{{negotiated_concessions}}</script>

<!-- Room block: YOU own thead; tbody stays empty for data -->
<table class="…">
  <thead>
    <tr>
      <th>Room category</th><th>Dates</th><th>Nights</th>
      <th>Qty req.</th><th>Rate / night</th><th>Est. total</th>
    </tr>
  </thead>
  <tbody data-proposal-bind="verified_room_blocks"></tbody>
</table>

<div class="proposal-cta">{{cta_accept_button}}</div>
<script src="/proposal_binding_runtime.js"></script>
```

Preview/substitution fills each script with JSON from seed or live RFP; runtime hydrates the table.

---

## Identification cues (agent self-check)

- Run **structure identification** on each binding JSON (table vs list vs object) — see table at top of this doc.
- Seeing `{{verified_room_blocks}}` → expect **`line_items` array** + **`summary` object** in JSON script; visible region stays empty for table bind.
- Seeing `line_items` in docs/user message → **table body is array-driven**; do not paste `<tr>` with live rates in template source.
- Seeing `items` on concessions → **list UI**, not one paragraph placeholder.
- Seeing `blocks` only in API cards → legacy; still design for **`line_items`** columns in the proposal.
- **Never** expect guests to read raw JSON — if preview shows `{` in a headline, template used token-only copy without display hydration; add `[data-proposal-field]` or rely on compile display rules.
