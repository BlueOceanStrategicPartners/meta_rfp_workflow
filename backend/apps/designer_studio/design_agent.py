"""Designer Studio — Muse Spark 1.3 for generation and validation."""
from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.designer_studio.media_service import format_assets_for_agent
from apps.designer_studio.models import REQUIRED_PLACEHOLDERS
from apps.designer_studio.services import compile_template, deterministic_template_checks
from apps.rfp_debate.meta_client import MetaModelClient

from .venue_map_context import build_default_map_agent_context

DESIGNER_SYSTEM_PROMPT = (
    "You are the Proposal Template Architect for a hospitality RFP platform. "
    "Return JSON only with keys: assistant_message (string), html_markup (string), "
    "css_stylesheet (string), js_script (string), "
    "clarification_options (optional string array of short clickable replies when you need input). "
    f"html_markup MUST include every binding token exactly once: "
    f"{', '.join(REQUIRED_PLACEHOLDERS)}. "
    "For {{selected_map_svg}}: use a venue-map-proposal section with "
    "<div class='venue-map-slot'>{{selected_map_svg}}</div> — the platform injects the "
    "system default interactive map at preview time; never leave the slot empty or use a tiny placeholder SVG. "
    "Put interactivity in js_script (no inline onclick). "
    "Embed uploaded images/videos using the absolute URLs provided in the attachments block. "
    "Use semantic HTML5, responsive CSS Grid/Flexbox, and {{cta_accept_button}} for accept CTA. "
    "If attachments are ambiguous, ask a clarifying question in assistant_message before major layout changes."
)

VALIDATION_SYSTEM_PROMPT = (
    "You validate compiled hospitality proposal HTML/CSS/JS templates. "
    "Return JSON only: valid (boolean), issues (string array), summary (string). "
    "Check placeholders, media embeds, CTA visibility, responsive layout, and JS safety."
)


class DesignerStudioAgent:
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
        venue_map_block: str = "",
    ) -> dict[str, Any]:
        user_payload = (
            f"{venue_map_block}\n\n"
            f"{attachment_block}\n\n"
            f"Current html_markup:\n{html_markup or '<empty>'}\n\n"
            f"Current css_stylesheet:\n{css_stylesheet or '<empty>'}\n\n"
            f"Current js_script:\n{js_script or '<empty>'}\n\n"
            f"Designer request:\n{message.strip()}"
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": DESIGNER_SYSTEM_PROMPT},
        ]
        for turn in history[-20:]:
            role = turn.get("role", "user")
            if role not in {"user", "assistant"}:
                continue
            messages.append({"role": role, "content": str(turn.get("content", ""))[:8000]})
        messages.append({"role": "user", "content": user_payload})

        raw = self.client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=messages,
            fixture_kind="designer_chat",
        )
        assistant = str(raw.get("assistant_message") or raw.get("message") or "").strip()
        html = str(raw.get("html_markup") or html_markup or "").strip()
        css = str(raw.get("css_stylesheet") or css_stylesheet or "").strip()
        js = str(raw.get("js_script") or js_script or "").strip()
        if not assistant:
            assistant = "Updated the proposal template layout, styles, and interactions."
        options = raw.get("clarification_options") or []
        if isinstance(options, list):
            clarification_options = [str(o) for o in options if o][:6]
        else:
            clarification_options = []
        if not clarification_options and "?" in assistant:
            clarification_options = ["Use hero placement", "Use gallery grid", "Skip media for now"]
        return {
            "assistant_message": assistant,
            "html_markup": html,
            "css_stylesheet": css,
            "js_script": js,
            "clarification_options": clarification_options,
            "model_id": settings.META_MODEL_SPARK,
        }

    def validate_layout(
        self,
        *,
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
        compiled_html: str | None = None,
    ) -> dict[str, Any]:
        deterministic_issues = deterministic_template_checks(html_markup, css_stylesheet, js_script)
        compiled = compiled_html or compile_template(html_markup, css_stylesheet, js_script=js_script)

        messages = [
            {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Template HTML (tokens):\n{html_markup[:10000]}\n\n"
                    f"CSS:\n{css_stylesheet[:6000]}\n\n"
                    f"JS:\n{js_script[:6000]}\n\n"
                    f"Compiled preview:\n{compiled[:10000]}"
                ),
            },
        ]
        raw = self.client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=messages,
            fixture_kind="designer_validate",
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
                or ("Template passes validation." if valid else "Template needs fixes.")
            ),
            "model_id": settings.META_MODEL_SPARK,
            "deterministic_issues": deterministic_issues,
            "muse_issues": muse_issues,
        }
