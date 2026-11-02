from types import SimpleNamespace

from apps.designer_studio.attachment_context import (
    AttachmentRole,
    classify_attachment_role,
    default_message_for_attachments,
    floorplan_image_urls,
    format_assets_for_agent,
)
from apps.designer_studio.context_budget import assemble_context_prefix, trim_context_block
from apps.designer_studio.models import MediaAssetType


def _asset(name: str, asset_id: str = "00000000-0000-0000-0000-000000000001", **meta):
    return SimpleNamespace(
        id=asset_id,
        original_name=name,
        media_type=MediaAssetType.IMAGE,
        metadata_json=meta,
    )


def test_pasted_screenshot_classified_layout_reference():
    asset = _asset("pasted-screenshot-2026-11-02T04-43-55.png", url="http://x/a.png")
    role = classify_attachment_role(message="", asset=asset)
    assert role == AttachmentRole.LAYOUT_REFERENCE


def test_floorplan_urls_exclude_screenshots():
    shot = _asset("pasted-screenshot-2026.png", "id-shot", url="http://x/shot.png")
    plan = _asset("hotel-floorplan.png", "id-plan", url="http://x/plan.png")
    urls = floorplan_image_urls("attach floorplan for the map", [shot, plan])
    assert urls == ["http://x/plan.png"]


def test_format_assets_for_agent_forbids_embed_on_screenshot():
    asset = _asset("pasted-screenshot-2026.png", url="http://x/shot.png")
    block = format_assets_for_agent([asset], message="see screenshot — header overlaps")
    assert "layout_reference" in block
    assert "FORBIDDEN" in block
    assert "http://x/shot.png" in block


def test_default_message_attachments_only_screenshot():
    asset = _asset("pasted-screenshot-2026.png", url="http://x/shot.png")
    msg = default_message_for_attachments("", [asset])
    assert "do not embed" in msg.lower()


def test_assemble_context_prefix_keeps_attachment_over_map():
    attachment = "A" * 2000 + " attachment intent"
    map_block = "M" * 8000
    att_trim = trim_context_block(attachment, kind="attachment")
    map_trim = trim_context_block(map_block, kind="map")
    combined = assemble_context_prefix([att_trim, map_trim], max_total=5000)
    assert "attachment intent" in combined
    assert len(combined) <= 5001
