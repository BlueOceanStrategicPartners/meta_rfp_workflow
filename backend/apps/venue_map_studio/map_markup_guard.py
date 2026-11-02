"""Keep InteractiveVenueMap storage and previews limited to the interactive map fragment."""
from __future__ import annotations

import re

from apps.designer_studio.models import REQUIRED_PLACEHOLDERS

_PROPOSAL_MARKERS = tuple(REQUIRED_PLACEHOLDERS) + (
    "venue-map-proposal",
    "proposal-venue-map",
    "proposal-cta",
    "Explore the Floorplate",
)

_ROOT_OPEN = re.compile(
    r"<div[^>]*(?:\bvenue-map-root\b|\bid=[\"']venue-map[\"'])[^>]*>",
    re.IGNORECASE,
)


def looks_like_proposal_body(html: str) -> bool:
    text = html or ""
    if any(token in text for token in _PROPOSAL_MARKERS):
        return True
    if re.search(r"<header\b|<footer\b|class=[\"'][^\"']*\bhero\b", text, re.I):
        return True
    return False


def _slice_balanced_div(html: str, start: int) -> str:
    depth = 0
    i = start
    n = len(html)
    while i < n:
        lower = html[i : i + 5].lower()
        if lower.startswith("<div"):
            depth += 1
            close = html.find(">", i)
            if close < 0:
                break
            i = close + 1
            continue
        if lower.startswith("</div"):
            depth -= 1
            end = html.find(">", i)
            i = (end + 1) if end >= 0 else i + 6
            if depth == 0:
                return html[start:i]
            continue
        i += 1
    return html[start:]


def extract_interactive_map_markup(html: str) -> str:
    """
    Return the interactive map root subtree, or empty if the body is proposal-only noise.
    """
    text = (html or "").strip()
    if not text:
        return ""

    match = _ROOT_OPEN.search(text)
    if match:
        fragment = _slice_balanced_div(text, match.start()).strip()
        if fragment:
            return fragment

    if looks_like_proposal_body(text) and "data-location-id" not in text.lower():
        return ""

    if "data-location-id" in text.lower() or "map-popup" in text.lower():
        return text

    if looks_like_proposal_body(text):
        return ""

    return text


def normalize_map_record_markup(html: str) -> tuple[str, list[str]]:
    """Sanitize before save or API read; returns (markup, warnings)."""
    warnings: list[str] = []
    original = (html or "").strip()
    if not original:
        return "", warnings

    cleaned = extract_interactive_map_markup(original)
    if not cleaned and original:
        warnings.append("Map markup looked like a full proposal page; stored map body cleared.")
        return "", warnings

    if cleaned != original:
        if looks_like_proposal_body(original):
            warnings.append("Removed proposal sections from venue map markup; kept map root only.")
        else:
            warnings.append("Trimmed venue map markup to the interactive map root.")

    return cleaned, warnings
