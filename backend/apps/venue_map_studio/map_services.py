"""Map fragment validation and compile helpers (no Map Studio DB)."""
from __future__ import annotations

from typing import Any

from apps.core.exceptions import TemplateValidationException
from apps.designer_studio.single_file_template import effective_style_and_script
from apps.designer_studio.services import compile_template
from apps.guardrails.validators import sanitize_template_html, sanitize_template_js


def compile_interactive_map(
    html: str,
    css: str = "",
    *,
    js_script: str = "",
) -> str:
    return compile_template(html, css, js_script=js_script, replacements={})


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
    _, eff_js = effective_style_and_script(html, css, js_script)
    if not (html or "").strip():
        issues.append("Map html_markup is empty; the agent must generate interactive map markup.")
    lower_html = (html or "").lower()
    if "venue-map-root" not in lower_html and 'id="venue-map"' not in lower_html and "id='venue-map'" not in lower_html:
        issues.append(
            "Map html_markup must use a single root <div class='venue-map-root' id='venue-map'>."
        )
    if "{{selected_map_svg}}" in (html or "") or "{{client_name}}" in (html or ""):
        issues.append("Map fragment must not include proposal binding tokens — only the interactive map root.")
    try:
        sanitize_template_html(html)
    except TemplateValidationException as exc:
        issues.append(str(exc))
    try:
        sanitize_template_js(eff_js)
    except TemplateValidationException as exc:
        issues.append(str(exc))
    lower_js = (eff_js or "").lower()
    if "postmessage" not in lower_js:
        issues.append(
            "Map JavaScript must call window.parent.postMessage with type venue-map-select when a zone opens."
        )
    if "popup" not in lower_js and "openlocation" not in lower_js.replace("-", ""):
        issues.append("Map JavaScript should open an in-map popup panel (e.g. openLocation + #map-popup).")
    if "mouseenter" not in lower_js and "pointerenter" not in lower_js and "click" not in lower_js:
        issues.append("Map JavaScript should wire hover or click on data-location-id markers.")
    locs = locations or []
    if not locs:
        issues.append("At least one location entry is required in the locations array.")
    else:
        markup_ids = extract_location_ids_from_markup(html, eff_js)
        for loc in locs:
            loc_id = str(loc.get("id") or loc.get("location_id") or "").strip()
            if not loc_id:
                issues.append("Each location must include a stable id.")
                continue
            if loc_id not in markup_ids and loc_id not in (html + eff_js):
                issues.append(f"Location id '{loc_id}' not found in HTML/JS markup.")
            if not str(loc.get("label") or loc.get("name") or "").strip():
                issues.append(f"Location '{loc_id}' is missing a label.")
    return issues
