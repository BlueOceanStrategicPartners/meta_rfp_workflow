"""Normalize generated map HTML/JS so popups do not cover the proposal on load."""
from __future__ import annotations

import re


def normalize_map_interaction(html: str, css: str, js: str) -> tuple[str, str, str]:
    html_out = html or ""
    css_out = css or ""
    js_out = js or ""

    if "map-popup" in html_out.lower():
        html_out = re.sub(
            r'(<[^>]*\bid=["\']map-popup["\'][^>]*\bclass=["\'])([^"\']*)(["\'])',
            _ensure_hidden_class,
            html_out,
            count=1,
            flags=re.I,
        )
        if "map-popup" in html_out and "hidden" not in html_out.lower():
            html_out = html_out.replace(
                "id='map-popup'",
                "id='map-popup' class='map-popup hidden'",
                1,
            )

    if ".map-popup.hidden" not in css_out and "map-popup" in css_out.lower():
        css_out = (css_out.rstrip() + "\n.map-popup.hidden{display:none!important;}\n").strip()

    if "map-popup" in html_out.lower() and "closePopup" not in js_out:
        js_out = (
            js_out.rstrip()
            + "\nfunction closePopup(){var p=document.getElementById('map-popup');"
            "if(p){p.classList.add('hidden');p.setAttribute('aria-hidden','true');}}\n"
        ).strip()

    if "map-popup" in html_out.lower() and "positionPopupNearMarker" not in js_out:
        from apps.venue_map_studio.map_popup_anchor import (
            MAP_POPUP_ANCHOR_CSS,
            MAP_POPUP_ANCHOR_SCRIPT,
        )

        js_out = (js_out.rstrip() + "\n" + MAP_POPUP_ANCHOR_SCRIPT).strip()
        if "positionPopupNearMarker" not in css_out and ".map-popup" in css_out.lower():
            css_out = (css_out.rstrip() + "\n" + MAP_POPUP_ANCHOR_CSS).strip()

    return html_out, css_out, js_out


def _ensure_hidden_class(match: re.Match[str]) -> str:
    prefix, classes, suffix = match.group(1), match.group(2), match.group(3)
    if "hidden" not in classes.split():
        classes = (classes + " hidden").strip()
    return prefix + classes + suffix
