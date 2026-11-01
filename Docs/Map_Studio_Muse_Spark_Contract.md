# Map Studio — Muse Spark 1.3 contract

Map Studio mirrors Designer Studio: **the AI agent builds the entire interactive map** from a floorplan image and/or natural-language description. Authors do not manually draw polygons or tag zones by hand.

## Agent JSON response (chat)

Required keys:

- `assistant_message` (string)
- `html_markup` (string) — clickable regions use `data-location-id` matching location ids
- `css_stylesheet` (string)
- `js_script` (string) — popups with label, description, images; must `postMessage` to parent:
  - `{ type: 'venue-map-select', locationId, label, description, imageUrls }`
- `locations` (array) — `{ id, label, description, image_urls[] }`
- `clarification_options` (optional string[])

## Validation (Spark + deterministic)

Before save as default, backend checks:

- Sanitized HTML/JS (guardrails)
- Every location id appears in markup/JS
- JS exposes popup/modal behavior and parent `postMessage`
- Muse Spark validation summary via `/api/maps/validate/`

## Media

Upload floorplans and location photos via `/api/maps/assets/upload/` (linked to `venue_map_id`). The agent embeds absolute URLs in popups.

## Client panel

`GET /api/maps/published/` returns `compiled_html` and `locations[]` for the default map. The client side panel listens for `venue-map-select` postMessage and supports downloading location detail JSON.

## Roles

`DESIGNER` and `ADMIN` may use Map Studio APIs. Legacy SAM vectorize endpoints remain for compatibility but AI chat generation is the primary workflow.
