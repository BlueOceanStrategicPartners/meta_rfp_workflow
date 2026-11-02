"""Normalize proposal templates to single-file html_markup (css/js cleared)."""
from __future__ import annotations

from .map_interaction_normalize import normalize_map_interaction
from .single_file_template import template_storage_mode


def normalize_proposal_template_fields(
    html_markup: str,
    css_stylesheet: str = "",
    js_script: str = "",
) -> tuple[str, str, str]:
    html = html_markup or ""
    css = css_stylesheet or ""
    js = js_script or ""
    if template_storage_mode(html, css, js) == "legacy" and (css.strip() or js.strip()):
        html, css, js = normalize_map_interaction(html, css, js)
        return html, css, js
    html, _, _ = normalize_map_interaction(html, "", "")
    return html, "", ""
