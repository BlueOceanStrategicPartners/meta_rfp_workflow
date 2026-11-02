"""Default system venue map — agent context and proposal {{selected_map_svg}} injection."""
from __future__ import annotations

import html as html_module
import re
from typing import Any

from apps.inventory.models import InteractiveVenueMap
from apps.venue_map_studio.map_services import compile_interactive_map, zone_detail_bundle

MAP_SLOT_CSS = (
    ".venue-map-proposal,.venue-map-slot{min-height:420px;width:100%;max-width:100%;}"
    ".proposal-venue-map-frame,.venue-map-slot iframe{width:100%;min-height:420px;border:0;"
    "border-radius:12px;display:block;background:#0f172a;}"
)

MAP_SECTION_SNIPPET = (
    "<section class='venue-map-proposal' aria-label='Interactive venue map'>"
    "<h2>Venue map</h2>"
    "<div class='venue-map-slot'>{{selected_map_svg}}</div>"
    "<p class='venue-map-caption'>Default property map — updates when the default venue map changes.</p>"
    "</section>"
)

_VENUE_MAP_SECTION_RE = re.compile(
    r"<section[^>]*\bvenue-map-proposal\b[^>]*>.*?</section>",
    re.DOTALL | re.IGNORECASE,
)


def get_default_venue_map() -> InteractiveVenueMap | None:
    return (
        InteractiveVenueMap.objects.filter(is_default=True)
        .prefetch_related("zones")
        .first()
    )


def default_map_locations(venue_map: InteractiveVenueMap) -> list[dict[str, Any]]:
    return [zone_detail_bundle(z) for z in venue_map.zones.all()]


def embed_compiled_map_document(compiled_html: str) -> str:
    """HTML fragment placed at {{selected_map_svg}} in proposal templates."""
    escaped = html_module.escape(compiled_html, quote=True)
    return (
        '<section class="proposal-venue-map venue-map-slot" data-system-default-map="true">'
        '<iframe class="proposal-venue-map-frame" title="Interactive venue map" '
        f'sandbox="allow-scripts allow-same-origin" loading="lazy" srcdoc="{escaped}"></iframe>'
        "</section>"
    )


def default_map_embed_for_proposal() -> str | None:
    venue_map = get_default_venue_map()
    if not venue_map or not (venue_map.html_markup or "").strip():
        return None
    compiled = compile_interactive_map(
        venue_map.html_markup,
        venue_map.css_stylesheet,
        js_script=venue_map.js_script,
    )
    return embed_compiled_map_document(compiled)


def build_map_library_summary(user) -> str:
    """Short list of saved maps for the design agent."""
    from apps.inventory.models import InteractiveVenueMap

    qs = InteractiveVenueMap.objects.all().order_by("-updated_at")
    if getattr(user, "role", None) != "ADMIN":
        qs = qs.filter(created_by=user)
    maps = list(qs[:12])
    if not maps:
        return "MAP LIBRARY: (empty — user can create maps via chat or floorplan upload.)"
    lines = []
    for m in maps:
        flag = " [DEFAULT]" if m.is_default else ""
        revs = len(m.revision_history_json or [])
        lines.append(f"  - {m.id} | {m.title}{flag} | {revs} revision(s)")
    return (
        "MAP LIBRARY (manage via chat: list maps, set default, delete map; "
        "or Venue maps panel in Live preview):\n" + "\n".join(lines)
    )


def remove_map_slot_from_template(html_markup: str) -> str:
    """Remove venue map section / placeholder from proposal HTML (library maps unchanged)."""
    html = html_markup or ""
    cleaned, n = _VENUE_MAP_SECTION_RE.subn("", html, count=1)
    if n:
        return cleaned.strip()
    if "{{selected_map_svg}}" not in html:
        return html
    html = html.replace(MAP_SECTION_SNIPPET, "")
    html = re.sub(
        r"<div[^>]*\bvenue-map-slot\b[^>]*>\s*\{\{selected_map_svg\}\}\s*</div>",
        "",
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    html = html.replace("{{selected_map_svg}}", "")
    return html.strip()


def build_default_map_agent_context(user=None) -> str:
    venue_map = get_default_venue_map()
    if not venue_map:
        base = (
            "SYSTEM VENUE MAP: none marked is_default. "
            "User can create maps in chat or use Venue maps in Live preview. "
            "Still include {{selected_map_svg}} inside .venue-map-slot when they want a map section."
        )
        if user is not None:
            base = base + "\n" + build_map_library_summary(user)
        return base
    locations = default_map_locations(venue_map)
    loc_lines = [
        f"  - {loc.get('id')}: {loc.get('label')} — {(loc.get('description') or '')[:120]}"
        for loc in locations[:12]
    ]
    markup_preview = (venue_map.html_markup or "")[:1200]
    base = (
        "SYSTEM DEFAULT VENUE MAP (is_default=true):\n"
        f"- map_id: {venue_map.id}\n"
        f"- title: {venue_map.title}\n"
        f"- locations ({len(locations)}):\n"
        + ("\n".join(loc_lines) if loc_lines else "  - (no zones yet)\n")
        + "\n"
        "PROPOSAL PLACEHOLDER RULES:\n"
        "- Keep exactly one {{selected_map_svg}} token in html_markup.\n"
        "- Place it inside <div class='venue-map-slot'> within a <section class='venue-map-proposal'>.\n"
        "- Do NOT replace {{selected_map_svg}} with inline SVG only; the platform injects the full "
        "interactive default map at preview/render time.\n"
        "- Add CSS for .venue-map-slot and iframe (min-height ~420px, width 100%, rounded corners).\n"
        "- When the user asks to show, fix, or add the map, ensure that section + token exist; "
        "merge map slot CSS into css_stylesheet if missing.\n"
        "- Map library actions (list / delete / set default / remove from proposal) are handled by the platform — "
        "do not ask the user to use a separate Map Studio.\n"
        f"- Reference markup excerpt (for structure only, do not duplicate ids blindly):\n{markup_preview}\n"
    )
    if user is not None:
        base = base + "\n" + build_map_library_summary(user) + "\n"
    return base


def inject_map_section_into_template(html_markup: str, css_stylesheet: str) -> dict[str, str]:
    """Ensure proposal has a map section and slot CSS (designer toolbar helper)."""
    html = html_markup or ""
    css = css_stylesheet or ""
    if "{{selected_map_svg}}" not in html:
        html = html + MAP_SECTION_SNIPPET
    elif "venue-map-slot" not in html and "{{selected_map_svg}}" in html:
        html = html.replace(
            "{{selected_map_svg}}",
            "<div class='venue-map-slot'>{{selected_map_svg}}</div>",
            1,
        )
    if "venue-map-slot" not in css and "proposal-venue-map-frame" not in css:
        css = (css.rstrip() + "\n" + MAP_SLOT_CSS).strip()
    return {"html_markup": html, "css_stylesheet": css}


def default_map_designer_payload() -> dict[str, Any]:
    venue_map = get_default_venue_map()
    if not venue_map:
        return {"available": False, "detail": "No default venue map. Create one via the Design Agent."}
    locations = default_map_locations(venue_map)
    compiled = compile_interactive_map(
        venue_map.html_markup,
        venue_map.css_stylesheet,
        js_script=venue_map.js_script,
    )
    return {
        "available": True,
        "id": str(venue_map.id),
        "title": venue_map.title,
        "locations": locations,
        "compiled_html": compiled,
        "embed_html": embed_compiled_map_document(compiled),
        "agent_context": build_default_map_agent_context(),
        "map_section_snippet": MAP_SECTION_SNIPPET,
        "map_slot_css": MAP_SLOT_CSS,
    }
