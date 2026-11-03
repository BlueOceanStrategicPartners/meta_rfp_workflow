"""Read UI cards snapshot and format for agent / voice prompts."""
from __future__ import annotations

from apps.rfp_debate.models import RFPSubmission


def read_cards_snapshot(rfp: RFPSubmission) -> dict:
    """Return active UI cards dict (empty sections as dicts)."""
    raw = rfp.active_ui_cards_json or {}
    return {
        "event_overview": dict(raw.get("event_overview") or {}),
        "room_block": dict(raw.get("room_block") or {}),
        "meeting_space": dict(raw.get("meeting_space") or {}),
        "live_quote": dict(raw.get("live_quote") or {}),
        "catering_av": dict(raw.get("catering_av") or {}),
    }


def format_cards_for_prompt(rfp: RFPSubmission) -> str:
    """Single-line-friendly summary for LLM context (no floor pricing)."""
    cards = read_cards_snapshot(rfp)
    overview = cards["event_overview"]
    meeting = cards["meeting_space"]
    room = cards["room_block"]
    quote = cards["live_quote"]

    lines = [f"RFP status: {rfp.status}."]
    org = overview.get("company_name")
    if org:
        lines.append(f"Organization: {org}.")
    if overview.get("check_in_date") or overview.get("check_out_date"):
        lines.append(
            f"Stay: {overview.get('check_in_date') or 'TBD'} to {overview.get('check_out_date') or 'TBD'}."
        )
    if room.get("total_room_nights"):
        lines.append(f"Room block: {room.get('total_room_nights')} nights.")
    if room.get("peak_rooms"):
        lines.append(f"Peak rooms: {room.get('peak_rooms')}.")
    if meeting.get("headcount"):
        lines.append(
            f"Meeting: {meeting.get('headcount')} guests, "
            f"{meeting.get('seating_style') or 'classroom'} seating."
        )
    anchor = quote.get("anchor_price")
    if anchor:
        lines.append(
            f"Preliminary package estimate (anchor): {anchor}. "
            "Do not mention floor or internal pricing."
        )
    return " ".join(lines)
