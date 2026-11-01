"""Map Studio — Muse Spark 1.3 for interactive map generation and validation."""
from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.designer_studio.media_service import format_assets_for_agent
from apps.designer_studio.services import compile_template
from apps.rfp_debate.meta_client import MetaModelClient
from apps.venue_map_studio.map_services import (
    compile_interactive_map,
    deterministic_map_checks,
)

MAP_SYSTEM_PROMPT = (
    "You are the Interactive Venue Map Architect for a hospitality RFP platform. "
    "The user provides a floorplan image and/or text description — you build the entire map; "
    "they never draw polygons manually. "
    "Return JSON only with keys: assistant_message (string), html_markup (string), "
    "css_stylesheet (string), js_script (string), locations (array), "
    "clarification_options (optional string array). "
    "Each locations[] item: id (stable slug), label, description (markdown-friendly plain text), "
    "image_urls (array of absolute URLs from attachments when provided). "
    "html_markup must define clickable regions using data-location-id matching each location id. "
    "js_script must: on location click, show an in-map popup with label, description, and images; "
    "and call window.parent.postMessage({type:'venue-map-select', locationId, label, description, imageUrls}, '*'). "
    "Use semantic HTML, responsive CSS, no inline onclick handlers. "
    "If a floorplan image URL is attached, use it as a background or reference layer in the layout."
)

MAP_VALIDATION_PROMPT = (
    "You validate compiled interactive hospitality venue maps (HTML/CSS/JS). "
    "Return JSON only: valid (boolean), issues (string array), summary (string). "
    "Check clickable zones, popup content, image embeds, location id consistency, and JS safety."
)


class MapStudioAgent:
    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    def chat_turn(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
        attachment_block: str = "",
    ) -> dict[str, Any]:
        user_payload = (
            f"{attachment_block}\n\n"
            f"Current html_markup:\n{html_markup or '<empty>'}\n\n"
            f"Current css_stylesheet:\n{css_stylesheet or '<empty>'}\n\n"
            f"Current js_script:\n{js_script or '<empty>'}\n\n"
            f"Map design request:\n{message.strip()}"
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": MAP_SYSTEM_PROMPT}]
        for turn in history[-20:]:
            role = turn.get("role", "user")
            if role not in {"user", "assistant"}:
                continue
            messages.append({"role": role, "content": str(turn.get("content", ""))[:8000]})
        messages.append({"role": "user", "content": user_payload})

        raw = self.client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=messages,
            fixture_kind="map_chat",
        )
        assistant = str(raw.get("assistant_message") or raw.get("message") or "").strip()
        html = str(raw.get("html_markup") or html_markup or "").strip()
        css = str(raw.get("css_stylesheet") or css_stylesheet or "").strip()
        js = str(raw.get("js_script") or js_script or "").strip()
        locations = raw.get("locations") or []
        if not isinstance(locations, list):
            locations = []
        if not assistant:
            assistant = "Updated the interactive venue map, zones, and location popups."
        options = raw.get("clarification_options") or []
        clarification_options = (
            [str(o) for o in options if o][:6] if isinstance(options, list) else []
        )
        if not clarification_options and "?" in assistant:
            clarification_options = ["Use ballroom labels", "Add photo gallery per zone", "Simplify layout"]
        return {
            "assistant_message": assistant,
            "html_markup": html,
            "css_stylesheet": css,
            "js_script": js,
            "locations": locations,
            "clarification_options": clarification_options,
            "model_id": settings.META_MODEL_SPARK,
        }

    def validate_map(
        self,
        *,
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
        locations: list[dict[str, Any]] | None = None,
        compiled_html: str | None = None,
    ) -> dict[str, Any]:
        locs = locations or []
        deterministic_issues = deterministic_map_checks(
            html_markup, css_stylesheet, js_script, locs
        )
        compiled = compiled_html or compile_interactive_map(
            html_markup, css_stylesheet, js_script=js_script
        )
        messages = [
            {"role": "system", "content": MAP_VALIDATION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Locations JSON:\n{locs[:20]}\n\n"
                    f"HTML:\n{html_markup[:10000]}\n\n"
                    f"CSS:\n{css_stylesheet[:6000]}\n\n"
                    f"JS:\n{js_script[:6000]}\n\n"
                    f"Compiled preview:\n{compiled[:10000]}"
                ),
            },
        ]
        raw = self.client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=messages,
            fixture_kind="map_validate",
        )
        muse_issues = [str(i) for i in (raw.get("issues") or []) if i]
        all_issues = deterministic_issues + muse_issues
        muse_valid = bool(raw.get("valid", not muse_issues))
        valid = not deterministic_issues and muse_valid and not muse_issues
        return {
            "valid": valid,
            "issues": all_issues,
            "summary": str(
                raw.get("summary")
                or ("Interactive map passes validation." if valid else "Map needs fixes.")
            ),
            "model_id": settings.META_MODEL_SPARK,
            "deterministic_issues": deterministic_issues,
            "muse_issues": muse_issues,
        }
