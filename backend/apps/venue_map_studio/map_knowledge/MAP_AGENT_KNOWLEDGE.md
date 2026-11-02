# Map Agent Knowledge — Interactive Venue Map Panel

**Canonical working example (open in browser):**  
`backend/apps/venue_map_studio/map_knowledge/interactive-venue-map-reference.html`

Use this document + HTML file as the **single source of truth** for Map Architect prompt engineering. Store the map as **one HTML file** in `html_markup` (Tailwind CDN + inline `<script>`). Set `css_stylesheet` and `js_script` to empty strings. Split the reference mentally into structure, utility classes, and script — but persist as a single document.

---

## Purpose

When the user attaches a **floorplan image**, the Design Agent builds the **venue map section inside the same proposal HTML** (not a separate service):

## Tailwind single-file

Embed the map as `<section class="venue-map-proposal">` with `.venue-map-root#venue-map` inside the proposal `html_markup`. Use Tailwind CDN utilities for layout; put marker/popup logic in an inline `<script>` in that file. Leave `css_stylesheet` and `js_script` empty.

- Floorplan as background (`img.map-floorplan`)
- Numbered **markers** positioned with `top` / `left` **percentages**
- **Hover / tap** opens an in-map **popup** (images, video, copy, action buttons)
- **Zone list** below stays in sync with markers
- `postMessage({ type: 'venue-map-select', ... })` for parent iframe

---

## MUST DO

| Rule | Detail |
|------|--------|
| Root element | One `<div class="venue-map-root" id="venue-map">` only — no proposal tokens |
| Floorplan | `<img class="map-floorplan" src="{attachment IMAGE url}">` inside `.map-stage` |
| Marker buttons | `type="button"` class `map-marker` + **`data-location-id="{slug}"`** |
| Marker position | **`style="top:NN%;left:MM%;"`** on every marker (align to rooms on the plan) |
| Zone list | `.map-zone-row` buttons with the **same** `data-location-id` as markers |
| Popup | `#map-popup.map-popup.hidden` inside `.map-stage`; hidden on load |
| Popup position | **`positionPopupNearMarker(id)`** after open — panel sits beside the hovered marker (not fixed top-right) |
| Active state | **`is-active` only in JavaScript** when a zone is open — never in initial HTML |
| Interaction | `addEventListener` for `click`, `mouseenter`, `focus`; `Escape` closes popup |
| locations[] JSON | One object per zone: `id`, `label`, `description`, `marker_x`, `marker_y`, `image_urls`, optional `video_urls`, `actions` |
| IDs match | Every `locations[].id` equals a `data-location-id` in HTML |

---

## MUST AVOID

| Anti-pattern | Why |
|--------------|-----|
| `style=""` or missing `top`/`left` on markers | All pins stack in one corner |
| `is-active` on markers/list in HTML | Everything looks selected; broken UX |
| Markers without `data-location-id` | Popups and sync break |
| Empty `.map-stage` when floorplan URL provided | Dark box with no plan |
| Full-screen fixed popup corner on desktop | Panel must track the marker being hovered |
| `{{selected_map_svg}}` inside map fragment | Deprecated — map is inline `.venue-map-proposal` in proposal html |
| Inline `onclick=` | Blocked / inconsistent with sanitizer |
| Guessing marker positions at 0,0 | Use plan-relative percentages (see reference HTML) |

---

## HTML skeleton (markers excerpt)

```html
<div class="map-stage">
  <img class="map-floorplan" src="https://…/floorplan.png" alt="Property floorplan" />
  <div class="map-markers" aria-label="Map zones">
    <button type="button" class="map-marker" data-location-id="grand-ballroom"
      style="top:48%;left:52%" aria-label="Grand Ballroom"><span>2</span></button>
  </div>
  <div id="map-popup" class="map-popup hidden" role="dialog" aria-hidden="true"></div>
</div>
```

---

## CSS essentials

- `.map-stage { position: relative; overflow: hidden; }`
- `.map-markers { position: absolute; inset: 0; pointer-events: none; }`
- `.map-marker { position: absolute; transform: translate(-50%, -50%); pointer-events: auto; }`
- `.map-popup { position: absolute; top: 0; left: 0; }` — **position set in JS** via `positionPopupNearMarker(id)`
- `.map-popup.hidden { display: none !important; }`

(Full rules in reference HTML `<style>` block — copy structure into `css_stylesheet`.)

---

## JavaScript essentials

- `LOCS` map keyed by `data-location-id`
- `positionPopupNearMarker(id)` → compute marker center inside `.map-stage`, set popup `left`/`top`, flip if near edge
- `openLocation(id)` → fill popup, remove `.hidden`, `setActive(id)`, **`requestAnimationFrame(() => positionPopupNearMarker(id))`**, `postMessage`
- `closePopup()` → add `.hidden`, clear `is-active`
- Wire `.map-marker` and `.map-zone-row` with shared `data-location-id`

(Full script in reference HTML — copy pattern into `js_script`.)

---

## locations[] example

```json
{
  "id": "grand-ballroom",
  "label": "Grand Ballroom",
  "description": "Divisible airwalls, dual projection.",
  "capacity_notes": "580 sqm • up to 600 theatre",
  "marker_x": 52,
  "marker_y": 48,
  "image_urls": ["https://…/ballroom.jpg"],
  "video_urls": [],
  "actions": [{ "label": "Request hold", "action": "request-hold" }]
}
```

`marker_x` / `marker_y` must match the marker’s `left` / `top` percentages in HTML.

---

## Verification checklist (before returning JSON)

1. Count markers === count `locations[]`
2. Every marker has non-empty `style` with `%` top and left
3. No `is-active` in html_markup
4. Every marker and list row has `data-location-id`
5. Floorplan `src` uses the user’s attached IMAGE url when provided
6. `#map-popup` has class `hidden`
7. JS contains `postMessage` and `openLocation` (or equivalent)

---

## Project wiring

- Backend contract: `backend/apps/venue_map_studio/map_component_contract.py`
- Map knowledge tools: `backend/apps/venue_map_studio/map_knowledge_tools.py`
- Map agent system prompt: inline in Design Agent (`design_agent.py` + map knowledge tools)
- Designer agent tools (tool loop):
  - `get_map_knowledge(topic=overview|checklist|do_dont|contract|locations_schema|all)`
  - `get_map_reference_code(part=html|css|js|markers|popup_anchor|structure|full, floorplan_url?)`
- HTTP (same payloads): `GET /api/designer/map-knowledge/?topic=all` or `?part=structure`
- Map stage context: `build_map_creation_context()` in orchestration

When updating prompts, **sync changes here and in `map_component_contract.py`.**
