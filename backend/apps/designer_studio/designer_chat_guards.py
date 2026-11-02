"""Pre-flight checks before expensive agent turns (attachments, preview issues)."""
from __future__ import annotations

import re
from typing import Any

from .preview_audit import audit_compiled_proposal_preview, format_preview_audit_for_agent

_FLOORPLAN_UPLOAD_PHRASES = (
    "upload floorplan",
    "upload a floorplan",
    "upload the floorplan",
    "attach floorplan",
    "attach a floorplan",
    "floorplan image",
    "i'll upload a floorplan",
    "ill upload a floorplan",
)

_PREVIEW_ISSUE_PHRASES = (
    "preview",
    "looks wrong",
    "not showing",
    "close button",
    "why now",
    "debug",
    "issue",
    "broken",
    "overlap",
    "hidden",
    "map always",
)


def _has_image_attachment(assets: list) -> bool:
    return any(getattr(a, "media_type", None) == "IMAGE" for a in assets)


def user_message_expects_floorplan_upload(message: str) -> bool:
    lower = (message or "").lower().strip()
    if not lower:
        return False
    if any(p in lower for p in _FLOORPLAN_UPLOAD_PHRASES):
        return True
    if "upload" in lower and "floor" in lower:
        return True
    if lower in {"upload floorplan image", "upload image", "attach image"}:
        return True
    return False


def try_floorplan_attachment_reminder(
    *,
    message: str,
    assets: list,
) -> dict[str, Any] | None:
    """If user asked to upload a floorplan but sent no image, respond immediately."""
    if not user_message_expects_floorplan_upload(message):
        return None
    if _has_image_attachment(assets):
        return None
    text = (
        "I don't see a floorplan attached on this message yet. "
        "Drag an image onto the chat, use the paperclip, or drop a file in the upload zone — "
        "then send again (you can send with attachments only). "
        "Once the floorplan is attached, I'll build the interactive map from it."
    )
    return {
        "assistant_message": text,
        "clarification_options": [
            "Skip questions — use a generic schematic map",
            "I'll attach the floorplan next",
        ],
        "attachment_required": True,
    }


def user_message_reports_preview_issue(message: str) -> bool:
    lower = (message or "").lower()
    return any(p in lower for p in _PREVIEW_ISSUE_PHRASES)


def build_preview_audit_block(html: str, css: str, js: str) -> str:
    findings = audit_compiled_proposal_preview(html, css, js)
    return format_preview_audit_for_agent(findings)
