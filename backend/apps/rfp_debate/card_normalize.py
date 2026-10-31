from __future__ import annotations

import re

from apps.rfp_debate.models import RFPSubmission


def normalize_cards_for_ui(rfp: RFPSubmission) -> None:
    """Ensure card deck can render after sparse voice or partial extraction."""
    cards = dict(rfp.active_ui_cards_json or {})
    overview = dict(cards.get("event_overview") or {})
    room = dict(cards.get("room_block") or {})
    meeting = dict(cards.get("meeting_space") or {})
    source = (rfp.source_document_text or "").strip()

    if not overview.get("company_name"):
        overview["company_name"] = "Your organization"
    if not overview.get("event_type"):
        overview["event_type"] = "Corporate event"

    nights_match = re.search(r"\b(\d+)\s*nights?\b", source, re.I)
    if nights_match:
        room["total_room_nights"] = int(nights_match.group(1))
    elif re.search(r"\bthree\b", source, re.I) and not room.get("total_room_nights"):
        room["total_room_nights"] = 3

    if not meeting.get("headcount") and room.get("total_room_nights"):
        meeting["headcount"] = 50

    cards["event_overview"] = overview
    cards["room_block"] = room
    cards.setdefault("meeting_space", meeting)
    cards.setdefault(
        "live_quote",
        {"anchor_price": None, "floor_price": None, "target_price": None},
    )
    cards.setdefault("catering_av", {"catering": None, "av": None})

    rfp.active_ui_cards_json = cards
    rfp.save(update_fields=["active_ui_cards_json", "updated_at"])
