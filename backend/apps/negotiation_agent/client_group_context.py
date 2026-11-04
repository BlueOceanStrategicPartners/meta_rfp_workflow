"""Remember group size across turns — cards, intake memory, and transcript."""
from __future__ import annotations

import re
from typing import Any

from apps.rfp_debate.models import RFPSubmission

from .client_session_memory import normalize_session


def participant_count_from_message(message: str) -> int | None:
    from .voice_card_updates import group_size_from_voice_message

    return group_size_from_voice_message(message)


def _intake(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get("intake")
    return raw if isinstance(raw, dict) else {}


def resolve_stored_headcount(rfp: RFPSubmission | None) -> int | None:
    if not rfp:
        return None
    cards = rfp.active_ui_cards_json or {}
    meeting = cards.get("meeting_space") or {}
    try:
        n = int(meeting.get("headcount") or 0)
        if n > 0:
            return n
    except (TypeError, ValueError):
        pass

    session = normalize_session(rfp.client_session_json)
    intake = _intake(session)
    try:
        n = int(intake.get("headcount") or 0)
        if n > 0:
            return n
    except (TypeError, ValueError):
        pass

    for turn in reversed(session.get("transcript") or []):
        if turn.get("role") != "user":
            continue
        from .voice_card_updates import group_size_from_voice_message

        c = group_size_from_voice_message(str(turn.get("text") or ""))
        if c:
            return c
    return None


def resolve_peak_rooms(rfp: RFPSubmission | None, *, headcount: int | None = None) -> int | None:
    if not rfp:
        return None
    cards = rfp.active_ui_cards_json or {}
    room = cards.get("room_block") or {}
    try:
        peak = int(room.get("peak_rooms") or 0)
        if peak > 0:
            return peak
    except (TypeError, ValueError):
        pass
    session = normalize_session(rfp.client_session_json)
    intake = _intake(session)
    try:
        peak = int(intake.get("peak_rooms") or 0)
        if peak > 0:
            return peak
    except (TypeError, ValueError):
        pass
    hc = headcount if headcount is not None else resolve_stored_headcount(rfp)
    return hc


def persist_group_size_to_intake(
    rfp: RFPSubmission,
    *,
    headcount: int | None = None,
    peak_rooms: int | None = None,
) -> None:
    session = normalize_session(rfp.client_session_json)
    intake = _intake(session)
    if headcount and headcount > 0:
        intake["headcount"] = str(headcount)
    if peak_rooms and peak_rooms > 0:
        intake["peak_rooms"] = str(peak_rooms)
    session["intake"] = intake
    rfp.client_session_json = session


def ensure_group_size_on_cards(rfp: RFPSubmission) -> None:
    """Merge intake/transcript headcount onto cards when a later turn only updates dates."""
    from .meeting_space_intent import meeting_space_wanted

    hc = resolve_stored_headcount(rfp)
    if not hc:
        return
    peak = resolve_peak_rooms(rfp, headcount=hc) or hc
    cards = dict(rfp.active_ui_cards_json or {})
    meeting = dict(cards.get("meeting_space") or {})
    room = dict(cards.get("room_block") or {})
    changed = False
    if meeting_space_wanted(rfp):
        if int(meeting.get("headcount") or 0) != hc:
            meeting["headcount"] = hc
            meeting["included"] = True
            changed = True
    if int(room.get("peak_rooms") or 0) != peak:
        room["peak_rooms"] = peak
        changed = True
    if not changed:
        return
    cards["meeting_space"] = meeting
    cards["room_block"] = room
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(str(rfp.id), {"meeting_space": meeting, "room_block": room})
    rfp.refresh_from_db()
    persist_group_size_to_intake(rfp, headcount=hc, peak_rooms=peak)


def spoken_headcount_confirm(headcount: int) -> str:
    return (
        f"You mentioned {headcount} participants — I'll keep that on your block "
        "unless you'd like to change it."
    )


def message_sets_new_headcount(message: str) -> bool:
    return participant_count_from_message(message) is not None or bool(
        re.search(r"\b(\d+)\s*(people|guests|attendees|pax)\b", (message or "").lower())
    )
