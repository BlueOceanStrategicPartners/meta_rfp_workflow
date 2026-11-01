"""Interactive venue map compile, zone sync, and deterministic validation."""
from __future__ import annotations

from typing import Any

from apps.core.exceptions import TemplateValidationException
from apps.designer_studio.services import compile_template
from apps.guardrails.validators import sanitize_template_html, sanitize_template_js
from apps.inventory.models import InteractiveVenueMap, VenueMapZone


def compile_interactive_map(
    html: str,
    css: str = "",
    *,
    js_script: str = "",
) -> str:
    return compile_template(html, css, js_script=js_script, replacements={})


def sync_locations_to_zones(
    venue_map: InteractiveVenueMap,
    locations: list[dict[str, Any]],
) -> list[VenueMapZone]:
    """Persist AI location metadata onto VenueMapZone rows."""
    zones: list[VenueMapZone] = []
    seen_ids: set[str] = set()
    for loc in locations:
        loc_id = str(loc.get("id") or loc.get("location_id") or "").strip()
        if not loc_id:
            continue
        seen_ids.add(loc_id)
        label = str(loc.get("label") or loc.get("name") or loc_id)
        description = str(loc.get("description") or "")
        image_urls = loc.get("image_urls") or loc.get("images") or []
        if isinstance(image_urls, str):
            image_urls = [image_urls]
        image_urls = [str(u) for u in image_urls if u][:12]
        meta = {
            "description": description,
            "image_urls": image_urls,
            "capacity_notes": loc.get("capacity_notes") or loc.get("capacity") or "",
            "features": loc.get("features") or [],
        }
        zone, _ = VenueMapZone.objects.update_or_create(
            venue_map=venue_map,
            svg_element_id=loc_id,
            defaults={
                "zone_label": label,
                "display_metadata_json": meta,
                "updated_by_agent": True,
            },
        )
        zones.append(zone)
    if seen_ids:
        VenueMapZone.objects.filter(venue_map=venue_map).exclude(
            svg_element_id__in=seen_ids
        ).delete()
    return zones


def extract_location_ids_from_markup(html: str, js: str) -> set[str]:
    import re

    combined = (html or "") + "\n" + (js or "")
    ids: set[str] = set()
    for pattern in (
        r'data-location-id=["\']([^"\']+)["\']',
        r'data-zone-id=["\']([^"\']+)["\']',
        r'id=["\']([^"\']+)["\']',
    ):
        ids.update(re.findall(pattern, combined))
    return {i for i in ids if i and not i.startswith("map-")}


def deterministic_map_checks(
    html: str,
    css: str = "",
    js_script: str = "",
    locations: list[dict[str, Any]] | None = None,
) -> list[str]:
    issues: list[str] = []
    if not (html or "").strip():
        issues.append("Map html_markup is empty; the agent must generate interactive map markup.")
    try:
        sanitize_template_html(html)
    except TemplateValidationException as exc:
        issues.append(str(exc))
    try:
        sanitize_template_js(js_script)
    except TemplateValidationException as exc:
        issues.append(str(exc))
    lower_js = (js_script or "").lower()
    if "postmessage" not in lower_js and "popup" not in lower_js and "modal" not in lower_js:
        issues.append(
            "Map JavaScript should open a popup/modal and/or postMessage location details on click."
        )
    locs = locations or []
    if not locs:
        issues.append("At least one location entry is required in the locations array.")
    else:
        markup_ids = extract_location_ids_from_markup(html, js_script)
        for loc in locs:
            loc_id = str(loc.get("id") or loc.get("location_id") or "").strip()
            if not loc_id:
                issues.append("Each location must include a stable id.")
                continue
            if loc_id not in markup_ids and loc_id not in (html + js_script):
                issues.append(f"Location id '{loc_id}' not found in HTML/JS markup.")
            if not str(loc.get("label") or loc.get("name") or "").strip():
                issues.append(f"Location '{loc_id}' is missing a label.")
    return issues


def zone_detail_bundle(zone: VenueMapZone) -> dict[str, Any]:
    meta = zone.display_metadata_json or {}
    return {
        "id": zone.svg_element_id,
        "location_id": zone.svg_element_id,
        "label": zone.zone_label,
        "description": meta.get("description") or "",
        "image_urls": meta.get("image_urls") or [],
        "capacity_notes": meta.get("capacity_notes") or "",
        "features": meta.get("features") or [],
        "space_inventory_id": str(zone.space_inventory_id) if zone.space_inventory_id else None,
    }
