"""Map Knowledge tools — DO/DON'T guides and reference code for Designer + Map Architect agents."""
from __future__ import annotations

import re
from typing import Any

from apps.venue_map_studio.map_component_contract import (
    MAP_COMPONENT_CONTRACT,
    MAP_KNOWLEDGE_HTML,
    MAP_KNOWLEDGE_MD,
    load_map_agent_knowledge_md,
    load_map_reference_html_excerpt,
)

MAP_KNOWLEDGE_TOOL_NAMES = frozenset(
    {
        "get_map_knowledge",
        "get_map_reference_code",
    }
)

_VALID_KNOWLEDGE_TOPICS = frozenset(
    {
        "overview",
        "checklist",
        "do_dont",
        "contract",
        "locations_schema",
        "all",
    }
)

_VALID_REFERENCE_PARTS = frozenset(
    {
        "html",
        "css",
        "js",
        "markers",
        "popup_anchor",
        "structure",
        "full",
    }
)


def _extract_style_block(html: str) -> str:
    match = re.search(r"<style[^>]*>(.*?)</style>", html, re.I | re.S)
    return match.group(1).strip() if match else ""


def _extract_script_block(html: str) -> str:
    match = re.search(r"<script[^>]*>(.*?)</script>", html, re.I | re.S)
    return match.group(1).strip() if match else ""


def _extract_body_inner(html: str) -> str:
    match = re.search(r"<body[^>]*>(.*?)</body>", html, re.I | re.S)
    return match.group(1).strip() if match else html


def _apply_floorplan_url(text: str, floorplan_url: str | None) -> str:
    if not floorplan_url:
        return text
    return re.sub(
        r'src="https?://[^"]+/media/designer_assets/[^"]+"',
        f'src="{floorplan_url}"',
        text,
        count=1,
    )


def _knowledge_checklist() -> str:
    return (
        "PRE-RETURN CHECKLIST:\n"
        "1. Count markers === count locations[]\n"
        "2. Every .map-marker has data-location-id + style top/left % (not empty)\n"
        "3. No is-active in html_markup from the model\n"
        "4. Every .map-zone-row has matching data-location-id\n"
        "5. img.map-floorplan uses attached floorplan URL when provided\n"
        "6. #map-popup has class hidden on load\n"
        "7. JS: openLocation, positionPopupNearMarker, postMessage venue-map-select\n"
    )


def _knowledge_do_dont() -> str:
    return (
        "MUST DO:\n"
        "- venue-map-root#venue-map only (no {{selected_map_svg}} in map fragment)\n"
        "- Markers: data-location-id + style=\"top:Y%;left:X%;\"\n"
        "- Popup anchored beside hovered marker via positionPopupNearMarker(id)\n"
        "- locations[] marker_x/marker_y match marker percentages\n\n"
        "MUST AVOID:\n"
        "- style=\"\" on markers (pins stack in one corner)\n"
        "- is-active in initial HTML\n"
        "- Fixed top-right popup only (must follow marker)\n"
        "- Missing data-location-id on markers or list rows\n"
    )


def _locations_schema() -> str:
    return (
        "locations[] schema (one object per zone):\n"
        "{\n"
        '  "id": "grand-ballroom",\n'
        '  "label": "Grand Ballroom",\n'
        '  "description": "…",\n'
        '  "capacity_notes": "580 sqm • up to 600 theatre",\n'
        '  "marker_x": 52,\n'
        '  "marker_y": 48,\n'
        '  "image_urls": ["https://…"],\n'
        '  "video_urls": [],\n'
        '  "actions": [{"label": "Request hold", "action": "request-hold"}]\n'
        "}\n"
    )


def execute_map_knowledge_tool(tool_name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments or {}
    name = (tool_name or "").strip()
    if name not in MAP_KNOWLEDGE_TOOL_NAMES:
        return {
            "ok": False,
            "error": f"Unknown map knowledge tool '{tool_name}'.",
        }

    if name == "get_map_knowledge":
        topic = str(args.get("topic") or "overview").strip().lower()
        if topic not in _VALID_KNOWLEDGE_TOPICS:
            return {
                "ok": False,
                "error": f"Invalid topic '{topic}'. Use: {sorted(_VALID_KNOWLEDGE_TOPICS)}",
            }
        content_parts: list[str] = []
        source = str(MAP_KNOWLEDGE_MD)
        if topic in ("overview", "all"):
            md = load_map_agent_knowledge_md()
            if md:
                content_parts.append(md[:12000])
            else:
                content_parts.append(MAP_COMPONENT_CONTRACT)
        if topic in ("checklist", "all"):
            content_parts.append(_knowledge_checklist())
        if topic in ("do_dont", "all"):
            content_parts.append(_knowledge_do_dont())
        if topic in ("contract", "all"):
            content_parts.append(MAP_COMPONENT_CONTRACT)
        if topic in ("locations_schema", "all"):
            content_parts.append(_locations_schema())
        return {
            "ok": True,
            "tool": name,
            "topic": topic,
            "source_path": source,
            "demo_html_path": str(MAP_KNOWLEDGE_HTML),
            "content": "\n\n---\n\n".join(content_parts).strip(),
        }

    part = str(args.get("part") or "structure").strip().lower()
    if part not in _VALID_REFERENCE_PARTS:
        return {
            "ok": False,
            "error": f"Invalid part '{part}'. Use: {sorted(_VALID_REFERENCE_PARTS)}",
        }
    floorplan_url = str(args.get("floorplan_url") or "").strip() or None
    try:
        raw_html = MAP_KNOWLEDGE_HTML.read_text(encoding="utf-8")
    except OSError:
        raw_html = load_map_reference_html_excerpt(max_chars=50000)

    raw_html = _apply_floorplan_url(raw_html, floorplan_url)
    css = _extract_style_block(raw_html)
    js = _extract_script_block(raw_html)
    body = _extract_body_inner(raw_html)

    if part == "html":
        payload = body
    elif part == "css":
        payload = css
    elif part == "js":
        payload = js
    elif part == "markers":
        markers = re.findall(
            r'<button[^>]*class="[^"]*map-marker[^"]*"[^>]*>.*?</button>',
            body,
            re.I | re.S,
        )
        payload = "\n".join(markers[:12]) or "No map-marker buttons found in reference."
    elif part == "popup_anchor":
        payload = ""
        if "function positionPopupNearMarker" in js:
            start = js.find("function positionPopupNearMarker")
            end = js.find("function closePopup", start)
            payload = js[start:end] if end > start else js[start : start + 2500]
        else:
            payload = "See get_map_reference_code part=js"
    elif part == "structure":
        payload = (
            "Reference fragment structure:\n"
            + body[:4500]
            + ("\n… [truncated]" if len(body) > 4500 else "")
        )
    else:
        payload = raw_html[:14000]
        if len(raw_html) > 14000:
            payload += "\n… [truncated — see backend/apps/venue_map_studio/map_knowledge/interactive-venue-map-reference.html]"

    return {
        "ok": True,
        "tool": name,
        "part": part,
        "floorplan_url": floorplan_url,
        "source_path": str(MAP_KNOWLEDGE_HTML),
        "content": payload,
        "hint": "Embed this pattern inside the proposal single-file HTML (Tailwind + inline script). css/js API fields stay empty.",
    }


def build_map_knowledge_for_proposal_agent(*, floorplan_urls: list[str] | None = None) -> str:
    """Short map knowledge block injected into Design Agent context (no separate map service)."""
    guide = execute_map_knowledge_tool("get_map_knowledge", {"topic": "overview"})
    checklist = execute_map_knowledge_tool("get_map_knowledge", {"topic": "checklist"})
    ref = execute_map_knowledge_tool("get_map_reference_code", {"part": "structure"})
    lines = [
        "INTERACTIVE VENUE MAP (part of the same proposal HTML document):",
        "- Build map markup inside <section class=\"venue-map-proposal\"> with .venue-map-root#venue-map.",
        "- Use get_map_knowledge / get_map_reference_code tools before editing the map section.",
        "- Tailwind utility classes + one inline <script> in html_markup — no separate css/js files.",
        "",
        str(guide.get("content") or "")[:4000],
        "",
        str(checklist.get("content") or "")[:2500],
        "",
        "REFERENCE SECTION (adapt to floorplan):",
        str(ref.get("content") or "")[:8000],
    ]
    if floorplan_urls:
        lines.insert(
            4,
            "FLOORPLAN URLS: " + ", ".join(floorplan_urls[:3]),
        )
    return "\n".join(lines).strip()


def build_map_creation_context(
    *,
    user_message: str = "",
    floorplan_url: str | None = None,
    include_full_reference: bool = False,
) -> str:
    """Structured context block for Map Architect turns (orchestration / chat)."""
    guide = execute_map_knowledge_tool("get_map_knowledge", {"topic": "all"})
    ref_part = execute_map_knowledge_tool(
        "get_map_reference_code",
        {"part": "structure" if not include_full_reference else "full", "floorplan_url": floorplan_url},
    )
    parts = [
        "MAP SECTION CONTEXT (embed in proposal html_markup — single Tailwind HTML file):",
        guide.get("content", "")[:10000],
        "",
        "REFERENCE CODE (copy/adapt into proposal map section):",
        str(ref_part.get("content", ""))[:12000],
    ]
    if floorplan_url:
        parts.insert(
            1,
            f"FLOORPLAN URL (use on img.map-floorplan): {floorplan_url}",
        )
    if user_message.strip():
        parts.append(f"USER MAP REQUEST:\n{user_message.strip()[:2000]}")
    return "\n\n".join(p for p in parts if p).strip()
