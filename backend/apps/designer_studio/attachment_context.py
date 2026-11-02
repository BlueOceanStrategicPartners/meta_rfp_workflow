"""Classify designer attachments and format agent context (screenshot vs floorplan vs embed media)."""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from apps.designer_studio.models import DesignerMediaAsset, MediaAssetType

from .designer_chat_guards import user_message_reports_preview_issue
from .placeholder_guidance import expand_guidance

_SCREENSHOT_NAME = re.compile(r"pasted-screenshot", re.I)

_LAYOUT_REFERENCE_PHRASES = (
    "screenshot",
    "screen shot",
    "snip",
    "paste",
    "pasted",
    "this area",
    "this section",
    "circled",
    "highlighted",
    "see attached",
    "see the image",
    "looks wrong",
    "layout issue",
    "preview issue",
    "broken",
    "overlap",
    "misaligned",
    "cut off",
    "not aligned",
)

_FLOORPLAN_PHRASES = (
    "floorplan",
    "floor plan",
    "floor-plan",
    "venue map",
    "interactive map",
    "map section",
    "zone map",
)

_EMBED_MEDIA_PHRASES = (
    "use this photo",
    "use this image",
    "hero image",
    "gallery",
    "brand photo",
    "property photo",
    "embed this",
    "put this image",
)


class AttachmentRole(StrEnum):
    LAYOUT_REFERENCE = "layout_reference"
    FLOORPLAN = "floorplan"
    PROPOSAL_MEDIA = "proposal_media"


def _message_blob(message: str) -> str:
    return (message or "").lower().strip()


def is_pasted_screenshot_name(name: str) -> bool:
    return bool(_SCREENSHOT_NAME.search(name or ""))


def classify_attachment_role(*, message: str, asset: DesignerMediaAsset) -> AttachmentRole:
    name = asset.original_name or ""
    meta = asset.metadata_json or {}
    stored = str(meta.get("attachment_role") or "")
    if stored in AttachmentRole._value2member_map_:
        return AttachmentRole(stored)

    lower = _message_blob(message)
    if is_pasted_screenshot_name(name):
        return AttachmentRole.LAYOUT_REFERENCE
    if user_message_reports_preview_issue(message) or any(p in lower for p in _LAYOUT_REFERENCE_PHRASES):
        if asset.media_type == MediaAssetType.IMAGE:
            return AttachmentRole.LAYOUT_REFERENCE
    if any(p in lower for p in _FLOORPLAN_PHRASES) and asset.media_type == MediaAssetType.IMAGE:
        return AttachmentRole.FLOORPLAN
    if any(p in lower for p in _EMBED_MEDIA_PHRASES):
        return AttachmentRole.PROPOSAL_MEDIA
    return AttachmentRole.PROPOSAL_MEDIA


def classify_attachments(message: str, assets: list[DesignerMediaAsset]) -> dict[str, AttachmentRole]:
    return {str(a.id): classify_attachment_role(message=message, asset=a) for a in assets}


def floorplan_image_urls(message: str, assets: list[DesignerMediaAsset]) -> list[str]:
    """URLs safe to pass to map knowledge (exclude layout-reference screenshots)."""
    roles = classify_attachments(message, assets)
    urls: list[str] = []
    for asset in assets:
        if asset.media_type != MediaAssetType.IMAGE:
            continue
        if roles.get(str(asset.id)) != AttachmentRole.FLOORPLAN:
            continue
        meta = asset.metadata_json or {}
        url = meta.get("url")
        if url:
            urls.append(str(url))
    return urls[:3]


def default_message_for_attachments(message: str, assets: list[DesignerMediaAsset]) -> str:
    text = (message or "").strip()
    if text:
        return text
    if not assets:
        return "Update the proposal template."
    roles = set(classify_attachments(message, assets).values())
    if roles == {AttachmentRole.LAYOUT_REFERENCE}:
        return (
            "Attached screenshot(s) show a layout/preview issue in the proposal. "
            "Fix the HTML/CSS structure — do not embed these files as proposal images."
        )
    return "Use the attached media according to each file role in the attachments block."


def format_assets_for_agent(
    assets: list[DesignerMediaAsset],
    *,
    message: str = "",
) -> str:
    if not assets:
        return ""
    roles = classify_attachments(message, assets)
    lines = [
        "ATTACHED FILES (roles are authoritative — obey per file):",
        expand_guidance("attachment_context.md"),
        "",
    ]
    for asset in assets:
        meta = asset.metadata_json or {}
        role = roles.get(str(asset.id), AttachmentRole.PROPOSAL_MEDIA)
        url = meta.get("url", "")
        name = meta.get("original_name", asset.original_name)
        if role == AttachmentRole.LAYOUT_REFERENCE:
            lines.append(
                f"- {name} [IMAGE role=layout_reference] "
                f"url={url} "
                "USE: visual reference for which section/element to fix in html_markup ONLY. "
                "FORBIDDEN: <img>, background-image, gallery, hero, card thumbnails, or map tiles."
            )
        elif role == AttachmentRole.FLOORPLAN:
            lines.append(
                f"- {name} [IMAGE role=floorplan] url={url} "
                "USE: .venue-map-proposal / interactive map section only — not marketing gallery."
            )
        else:
            desc = meta.get("description", "n/a")
            placement = meta.get("suggested_placement", "gallery")
            hint = meta.get("embed_hint", "Use <img> or <video controls> with absolute url")
            lines.append(
                f"- {name} [{asset.media_type} role=proposal_media] url={url} "
                f"description={desc} placement={placement} embed_hint={hint}"
            )
    return "\n".join(lines)


def patch_metadata_roles(assets: list[DesignerMediaAsset], message: str) -> None:
    """Persist attachment_role on assets after classify (for later turns / library)."""
    roles = classify_attachments(message, assets)
    for asset in assets:
        role = roles.get(str(asset.id))
        if not role:
            continue
        meta = dict(asset.metadata_json or {})
        if meta.get("attachment_role") == role:
            continue
        meta["attachment_role"] = role
        if role == AttachmentRole.LAYOUT_REFERENCE:
            meta["suggested_placement"] = "reference_only"
            meta.setdefault(
                "description",
                "Designer preview screenshot — layout reference, not guest-facing media",
            )
        asset.metadata_json = meta
        asset.save(update_fields=["metadata_json"])
