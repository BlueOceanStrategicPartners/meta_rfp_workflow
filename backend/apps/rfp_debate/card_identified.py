"""Whether UI cards hold client-identified data (not empty placeholders)."""
from __future__ import annotations

_PLACEHOLDER_ORGS = frozenset({"your organization", "your organisation", "voice rfp session"})


def cards_have_identified_fields(cards: dict | None) -> bool:
    if not isinstance(cards, dict) or not cards:
        return False
    overview = cards.get("event_overview") or {}
    room = cards.get("room_block") or {}
    meeting = cards.get("meeting_space") or {}
    quote = cards.get("live_quote") or {}

    org = str(overview.get("company_name") or "").strip().lower()
    if org and org not in _PLACEHOLDER_ORGS:
        return True

    for key in ("check_in_date", "check_out_date"):
        val = str(overview.get(key) or "").strip()
        if val and val.upper() != "TBD":
            return True

    if room.get("total_room_nights") or room.get("peak_rooms"):
        return True
    try:
        if int(meeting.get("headcount") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    if quote.get("anchor_price"):
        return True
    return False
