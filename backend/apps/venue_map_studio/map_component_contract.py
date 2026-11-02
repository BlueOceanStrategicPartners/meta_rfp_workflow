"""Prompt contract + canonical reference for Interactive Venue Map generation."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_MAP_STUDIO_ROOT = Path(__file__).resolve().parent
MAP_KNOWLEDGE_DIR = _MAP_STUDIO_ROOT / "map_knowledge"
MAP_KNOWLEDGE_HTML = MAP_KNOWLEDGE_DIR / "interactive-venue-map-reference.html"
MAP_KNOWLEDGE_MD = MAP_KNOWLEDGE_DIR / "MAP_AGENT_KNOWLEDGE.md"


@lru_cache(maxsize=1)
def load_map_agent_knowledge_md() -> str:
    """Full MAP_AGENT_KNOWLEDGE.md for map agent system / user context."""
    try:
        return MAP_KNOWLEDGE_MD.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@lru_cache(maxsize=1)
def load_map_reference_html_excerpt(max_chars: int = 12000) -> str:
    """Working single-file reference (for few-shot); truncated for token budget."""
    try:
        text = MAP_KNOWLEDGE_HTML.read_text(encoding="utf-8")
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n… [truncated — see backend/apps/venue_map_studio/map_knowledge/interactive-venue-map-reference.html]"


MAP_COMPONENT_CONTRACT = """
INTERACTIVE VENUE MAP — inline section inside the proposal single-file HTML (Tailwind + inline script)

Authoritative knowledge: backend/apps/venue_map_studio/map_knowledge/ (MAP_AGENT_KNOWLEDGE.md + interactive-venue-map-reference.html)
All map markup, styling (Tailwind utilities), and behavior (<script>) live in proposal html_markup. css_stylesheet and js_script stay empty.

SCOPE
- Add <section class="venue-map-proposal"> containing <div class="venue-map-root" id="venue-map">…</div>
- Never use {{selected_map_svg}} or separate map services — same document as hero, room blocks, and CTA.
- Never include proposal binding tokens inside map-only snippets.

LAYOUT (inside .venue-map-root)
1) Optional .map-header (title, subtitle, zone count badge).
2) .map-stage — position:relative; aspect-ratio ~16/10 or min-height 320px.
   - Floorplan: when attachments include an IMAGE with url=, set that URL on
     <img class="map-floorplan" alt="Property floorplan"> covering the stage (width:100%; height:100%; object-fit:contain).
     Do NOT leave .map-stage empty when a floorplan URL is provided.
   - Without a floorplan: use a subtle schematic background (CSS gradient/grid), still with labeled markers.
3) .map-markers — position:absolute; inset:0; pointer-events:none (markers re-enable pointer-events).
   - One <button type="button" class="map-marker" data-location-id="{id}"> per zone.
   - REQUIRED on every marker: data-location-id="{slug}" AND style="top:YY%;left:XX%;" (never empty style="").
   - marker_x/marker_y in locations[] MUST match left/top percentages in HTML.
4) Optional .map-zone-list — each .map-zone-row button MUST have the same data-location-id as its marker.
5) One shared popup: <div id="map-popup" class="map-popup hidden" role="dialog" aria-hidden="true"></div>
   - Popups MUST start hidden; never cover the map on load (no full-screen overlay until interaction).

NEVER in html_markup from the model
- class is-active on markers or zone rows (JS adds is-active only while popup is open)
- map-marker buttons missing data-location-id or missing top/left % positioning

INTERACTION (inline <script> in the same html_markup — addEventListener only, no inline onclick)
- positionPopupNearMarker(locationId): measure .map-marker center inside .map-stage; set #map-popup left/top beside marker (flip if overflow).
- openLocation(id): fill #map-popup with label, description, capacity line, images, videos, action buttons; remove .hidden;
  then requestAnimationFrame(function(){ positionPopupNearMarker(id); }).
- closePopup(): add .hidden to #map-popup.
- Triggers: pointerenter/focus on .map-marker opens popup (desktop hover); click togg/opens for touch; click list rows calls openLocation.
- Highlight active marker/list row while popup is open (class is-active).
- window.parent.postMessage({type:'venue-map-select', locationId, label, description, imageUrls, videoUrls}, '*') on openLocation.

POPUP CONTENT
- Images: <img> from location image_urls (absolute URLs from attachments when provided).
- Videos: <video controls playsinline> from location video_urls when present.
- Actions: optional location.actions[] as <a class="map-action"> or <button type="button" class="map-action" data-action="…">.

locations[] JSON (one entry per marker; ids must match data-location-id)
- id (slug), label, description, image_urls[], video_urls[] (optional),
  capacity_notes (optional string), marker_x / marker_y (required numbers 0–100 for placement),
  actions (optional): [{ "label": "…", "href": "https://…" }] or [{ "label": "…", "action": "request-hold" }].

QUALITY
- 4–8 zones for hospitality; professional copy; responsive CSS; semantic HTML; accessible focus rings on markers.
""".strip()


def pick_floorplan_url(attachment_block: str, instruction: str = "") -> str | None:
    """First IMAGE url from attachments, preferring names that look like floorplans."""
    combined = f"{attachment_block}\n{instruction}"
    image_lines = [
        ln
        for ln in combined.splitlines()
        if re.search(r"\[IMAGE\]", ln, re.I) and "url=" in ln
    ]
    candidates: list[tuple[int, str]] = []
    for line in image_lines:
        match = re.search(r"url=(https?://[^\s]+)", line)
        if not match:
            continue
        url = match.group(1)
        lower = line.lower()
        score = 0
        if any(k in lower for k in ("floorplan", "floor plan", "floor-plan", "floorplate", "map", "plan")):
            score += 10
        candidates.append((score, url))
    if candidates:
        candidates.sort(key=lambda t: (-t[0], t[1]))
        return candidates[0][1]
    urls = re.findall(r"url=(https?://[^\s]+)", combined)
    return urls[0] if urls else None


def build_reference_map_component(*, floorplan_url: str | None = None) -> dict[str, Any]:
    """
    Gold-standard map fragment for fixtures and few-shot prompting.
    """
    plan = floorplan_url or "https://placehold.co/1200x750/png?text=Floorplan"
    photo = "https://placehold.co/640x360/png?text=Zone+photo"
    locations: list[dict[str, Any]] = [
        {
            "id": "grand-ballroom",
            "label": "Grand Ballroom",
            "description": "Divisible airwalls, dual projection, pre-function foyer access.",
            "capacity_notes": "580 sqm • up to 600 theatre",
            "image_urls": [photo],
            "video_urls": [],
            "marker_x": 28,
            "marker_y": 38,
            "actions": [{"label": "Request hold", "action": "request-hold"}],
        },
        {
            "id": "sky-terrace",
            "label": "Sky Terrace & Gardens",
            "description": "Open-air terrace for welcome receptions and al-fresco dinners.",
            "capacity_notes": "220 guests cocktail",
            "image_urls": [photo],
            "video_urls": ["https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"],
            "marker_x": 62,
            "marker_y": 22,
            "actions": [{"label": "View gallery", "href": "#gallery-sky-terrace"}],
        },
    ]
    html = (
        "<div class='venue-map-root' id='venue-map'>"
        "<header class='map-header'>"
        "<p class='map-eyebrow'>Interactive resort map</p>"
        "<h2 class='map-title'>Explore the property</h2>"
        "<p class='map-lede'>Select a numbered zone on the plan or from the list.</p>"
        f"<p class='map-badge'>{len(locations)} zones • hover or tap to explore</p>"
        "</header>"
        "<div class='map-stage'>"
        f"<img class='map-floorplan' src='{plan}' alt='Property floorplan'/>"
        "<div class='map-markers' aria-label='Map zones'>"
        "<button type='button' class='map-marker' data-location-id='grand-ballroom' "
        "style='top:38%;left:28%' aria-label='Grand Ballroom'><span>1</span></button>"
        "<button type='button' class='map-marker' data-location-id='sky-terrace' "
        "style='top:22%;left:62%' aria-label='Sky Terrace'><span>2</span></button>"
        "</div>"
        "<div id='map-popup' class='map-popup hidden' role='dialog' aria-hidden='true'></div>"
        "</div>"
        "<ol class='map-zone-list'>"
        "<li><button type='button' class='map-zone-row' data-location-id='grand-ballroom'>"
        "<span class='map-zone-num'>1</span><span class='map-zone-copy'>"
        "<strong>Grand Ballroom</strong><em>580 sqm • up to 600 theatre</em>"
        "<span>Divisible airwalls and dual projection.</span></span></button></li>"
        "<li><button type='button' class='map-zone-row' data-location-id='sky-terrace'>"
        "<span class='map-zone-num'>2</span><span class='map-zone-copy'>"
        "<strong>Sky Terrace &amp; Gardens</strong><em>220 guests cocktail</em>"
        "<span>Open-air welcome receptions and dinners.</span></span></button></li>"
        "</ol>"
        "</div>"
    )
    css = """
.venue-map-root{font-family:system-ui,sans-serif;color:#0f172a;max-width:100%;}
.map-header{padding:1rem 1.25rem;background:#f8fafc;border-radius:16px;margin-bottom:0.75rem;}
.map-eyebrow{text-transform:uppercase;letter-spacing:0.08em;font-size:0.75rem;color:#b45309;margin:0;}
.map-title{font-family:Georgia,serif;font-size:1.75rem;margin:0.35rem 0;}
.map-lede{margin:0;color:#475569;font-size:0.95rem;}
.map-badge{display:inline-block;margin-top:0.75rem;padding:0.35rem 0.75rem;border-radius:999px;
background:#14532d;color:#ecfdf5;font-size:0.8rem;}
.map-stage{position:relative;background:#0f172a;border-radius:16px;overflow:hidden;min-height:320px;}
.map-floorplan{width:100%;height:auto;display:block;min-height:280px;object-fit:contain;background:#111827;}
.map-markers{position:absolute;inset:0;pointer-events:none;}
.map-marker{position:absolute;transform:translate(-50%,-50%);pointer-events:auto;width:2.5rem;height:2.5rem;
border-radius:999px;border:2px solid #fbbf24;background:rgba(15,23,42,0.85);color:#fef3c7;font-weight:700;
cursor:pointer;box-shadow:0 8px 24px rgba(0,0,0,0.35);}
.map-marker.is-active,.map-zone-row.is-active{outline:3px solid #38bdf8;outline-offset:2px;}
.map-marker span{display:block;line-height:2.25rem;text-align:center;}
.map-popup{position:absolute;top:0;left:0;right:auto;max-width:min(320px,88%);background:#fff;color:#0f172a;
padding:1rem;border-radius:14px;box-shadow:0 20px 50px rgba(0,0,0,0.45);z-index:20;max-height:min(420px,70vh);overflow:auto;}
.map-popup.hidden{display:none!important;}
.map-popup h3{margin:0 0 0.35rem;font-size:1.1rem;}
.map-popup .map-capacity{font-style:italic;color:#64748b;margin:0 0 0.5rem;font-size:0.85rem;}
.map-popup img,.map-popup video{max-width:100%;border-radius:10px;margin-top:0.5rem;display:block;}
.map-popup .map-actions{display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.75rem;}
.map-action{font-size:0.85rem;padding:0.45rem 0.75rem;border-radius:999px;border:1px solid #cbd5e1;
background:#f1f5f9;color:#0f172a;text-decoration:none;cursor:pointer;}
.map-zone-list{list-style:none;margin:0.75rem 0 0;padding:0;display:flex;flex-direction:column;gap:0.5rem;}
.map-zone-row{width:100%;text-align:left;display:flex;gap:0.75rem;padding:0.85rem 1rem;border:0;border-radius:12px;
background:#fff;box-shadow:0 1px 3px rgba(15,23,42,0.08);cursor:pointer;}
.map-zone-num{font-weight:800;font-size:1.1rem;min-width:2rem;}
.map-zone-copy{display:flex;flex-direction:column;gap:0.15rem;}
.map-zone-copy em{font-size:0.85rem;color:#64748b;}
.map-close{margin-top:0.5rem;font-size:0.8rem;background:transparent;border:0;color:#64748b;cursor:pointer;}
@media (max-width:640px){.map-popup{max-width:min(300px,92%);max-height:min(360px,55vh);}}
""".strip()
    js = """
(function(){
var LOCS={
  "grand-ballroom":{label:"Grand Ballroom",description:"Divisible airwalls, dual projection.",
    capacity:"580 sqm • up to 600 theatre",imageUrls:["PHOTO"],videoUrls:[],actions:[{label:"Request hold",action:"request-hold"}]},
  "sky-terrace":{label:"Sky Terrace & Gardens",description:"Open-air terrace for receptions.",
    capacity:"220 guests cocktail",imageUrls:["PHOTO"],videoUrls:["https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"],
    actions:[{label:"View gallery",href:"#gallery-sky-terrace"}]}
};
function esc(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");}
function mediaHtml(d){
  var h=(d.imageUrls||[]).map(function(u){return '<img src="'+esc(u)+'" alt=""/>';}).join("");
  h+=(d.videoUrls||[]).map(function(u){return '<video controls playsinline src="'+esc(u)+'"></video>';}).join("");
  return h;
}
function actionsHtml(d){
  var acts=d.actions||[];
  if(!acts.length)return "";
  return '<div class="map-actions">'+acts.map(function(a){
    if(a.href)return '<a class="map-action" href="'+esc(a.href)+'">'+esc(a.label)+'</a>';
    return '<button type="button" class="map-action" data-action="'+esc(a.action||"")+'">'+esc(a.label)+'</button>';
  }).join("")+'</div>';
}
function setActive(id){
  document.querySelectorAll(".map-marker,.map-zone-row").forEach(function(el){
    el.classList.toggle("is-active",el.getAttribute("data-location-id")===id);
  });
}
function closePopup(){
  var p=document.getElementById("map-popup");
  if(!p)return;
  p.classList.add("hidden");
  p.setAttribute("aria-hidden","true");
  setActive("");
}
function positionPopupNearMarker(locationId){
  var stage=document.querySelector(".map-stage");
  var popup=document.getElementById("map-popup");
  if(!stage||!popup)return;
  var marker=stage.querySelector('.map-marker[data-location-id="'+locationId+'"]');
  var pad=8,gap=14;
  if(!marker){popup.style.left=pad+"px";popup.style.top=pad+"px";return;}
  var sw=stage.clientWidth,sh=stage.clientHeight;
  var mr=marker.getBoundingClientRect(),sr=stage.getBoundingClientRect();
  var cx=mr.left-sr.left+mr.width/2,cy=mr.top-sr.top+mr.height/2;
  var pw=popup.offsetWidth||280,ph=popup.offsetHeight||120;
  var left=cx+gap,top=cy-ph/2;
  if(left+pw>sw-pad)left=cx-pw-gap;
  if(left<pad)left=pad;
  if(top+ph>sh-pad)top=sh-ph-pad;
  if(top<pad)top=pad;
  popup.style.left=Math.round(left)+"px";
  popup.style.top=Math.round(top)+"px";
  popup.style.right="auto";
}
function openLocation(id){
  var d=LOCS[id];
  if(!d)return;
  var p=document.getElementById("map-popup");
  if(!p)return;
  p.innerHTML='<h3>'+esc(d.label)+'</h3><p class="map-capacity">'+esc(d.capacity||"")+'</p><p>'+esc(d.description)+'</p>'
    +mediaHtml(d)+actionsHtml(d)+'<button type="button" class="map-close">Close</button>';
  p.classList.remove("hidden");
  p.setAttribute("aria-hidden","false");
  setActive(id);
  p.querySelector(".map-close").addEventListener("click",closePopup);
  requestAnimationFrame(function(){positionPopupNearMarker(id);});
  window.parent.postMessage({type:"venue-map-select",locationId:id,label:d.label,description:d.description,
    imageUrls:d.imageUrls||[],videoUrls:d.videoUrls||[]},"*");
}
document.querySelectorAll(".map-marker,.map-zone-row").forEach(function(el){
  var id=el.getAttribute("data-location-id");
  el.addEventListener("click",function(){openLocation(id);});
  el.addEventListener("mouseenter",function(){openLocation(id);});
  el.addEventListener("focus",function(){openLocation(id);});
});
document.addEventListener("keydown",function(e){if(e.key==="Escape")closePopup();});
})();
""".replace("PHOTO", photo)
    return {
        "html_markup": html,
        "css_stylesheet": css,
        "js_script": js,
        "locations": locations,
    }


def map_agent_few_shot_block(*, floorplan_url: str | None = None) -> str:
    """Compact reference appended to map agent user payload."""
    from apps.venue_map_studio.map_knowledge_tools import build_map_creation_context

    return build_map_creation_context(
        floorplan_url=floorplan_url,
        include_full_reference=False,
    )
