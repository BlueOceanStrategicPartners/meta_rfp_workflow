from __future__ import annotations

import re

from apps.rfp_debate.models import RFPSubmission

_PLACEHOLDER_ORGS = frozenset({"your organization", "your organisation", "voice rfp session"})


def _source_has_identified_fields(source: str, room: dict, meeting: dict) -> bool:
    if not source.strip():
        return False
    if re.search(r"\b(\d+)\s*(nights?|participants?|guests|rooms?)\b", source, re.I):
        return True
    if re.search(r"\bseveral rooms?\b|\bmultiple rooms?\b|\bnext week\b", source, re.I):
        return True
    return bool(room.get("total_room_nights") or room.get("peak_rooms") or meeting.get("headcount"))


def normalize_cards_for_ui(rfp: RFPSubmission, *, fill_placeholders: bool = True) -> None:
    """Ensure card deck can render after sparse voice or partial extraction."""
    cards = dict(rfp.active_ui_cards_json or {})
    overview = dict(cards.get("event_overview") or {})
    room = dict(cards.get("room_block") or {})
    meeting = dict(cards.get("meeting_space") or {})
    source = (rfp.source_document_text or "").strip()

    nights_match = re.search(r"\b(\d+)\s*nights?\b", source, re.I)
    if nights_match:
        room["total_room_nights"] = int(nights_match.group(1))
    elif re.search(r"\bthree\b", source, re.I) and not room.get("total_room_nights"):
        room["total_room_nights"] = 3

    participants_match = re.search(r"\b(\d+)\s*participants?\b", source, re.I)
    if participants_match:
        meeting["headcount"] = int(participants_match.group(1))
    if re.search(r"\bseveral rooms?\b|\bmultiple rooms?\b|\bnot one room\b", source, re.I):
        if meeting.get("headcount"):
            room["peak_rooms"] = int(meeting["headcount"])

    if not meeting.get("headcount") and room.get("total_room_nights") and fill_placeholders:
        from apps.negotiation_agent.meeting_space_intent import meeting_space_wanted

        if meeting_space_wanted(rfp):
            meeting["headcount"] = 50

    identified = _source_has_identified_fields(source, room, meeting) or fill_placeholders
    if fill_placeholders:
        if not overview.get("company_name"):
            overview["company_name"] = "Your organization"
        if not overview.get("event_type"):
            overview["event_type"] = "Corporate event"

    cards["event_overview"] = overview
    cards["room_block"] = room
    cards.setdefault("meeting_space", meeting)
    cards.setdefault(
        "live_quote",
        {"anchor_price": None, "floor_price": None, "target_price": None},
    )
    cards.setdefault("catering_av", {"catering": None, "av": None})

    rfp.active_ui_cards_json = cards
    from apps.negotiation_agent.client_session_memory import sync_clarifications_from_cards
    from apps.rfp_debate.card_identified import cards_have_identified_fields

    if identified and cards_have_identified_fields(cards):
        sync_clarifications_from_cards(rfp)
    else:
        session = rfp.client_session_json or {}
        if isinstance(session, dict):
            session = dict(session)
            session["clarification_options"] = []
            session["agent_todos"] = []
            rfp.client_session_json = session
    rfp.save(update_fields=["active_ui_cards_json", "client_session_json", "updated_at"])
