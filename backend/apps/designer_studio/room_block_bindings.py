"""Backward-compatible re-exports — use proposal_bindings for JSON seed + hydration."""
from __future__ import annotations

from .proposal_bindings import (
    build_binding_payloads_from_cards,
    build_binding_replacements,
    line_items_from_legacy_blocks,
    load_proposal_binding_seed,
    resolve_verified_room_blocks_payload,
    sample_binding_payloads,
)

# Legacy names used in tests / arbiter
SAMPLE_ROOM_BLOCK_LINE_ITEMS = (
    load_proposal_binding_seed().get("verified_room_blocks", {}).get("line_items") or []
)
SAMPLE_ROOM_BLOCK_SUMMARY = (
    load_proposal_binding_seed().get("verified_room_blocks", {}).get("summary") or {}
)


def resolve_room_block_summary(room_block, line_items, *, use_sample_if_empty=False):
    payload = resolve_verified_room_blocks_payload(
        room_block, use_seed_if_empty=use_sample_if_empty
    )
    return payload.get("summary") or {}


def sample_room_block_card_payload():
    vr = load_proposal_binding_seed()["verified_room_blocks"]
    return {
        "blocks": vr.get("blocks") or [],
        "line_items": vr.get("line_items") or [],
        "summary": vr.get("summary") or {},
        "total_room_nights": (vr.get("summary") or {}).get("room_nights"),
        "policy_notes": (vr.get("summary") or {}).get("policy_notes"),
    }
