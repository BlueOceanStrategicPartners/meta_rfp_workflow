"""Gate: room block sizing vs live guest-room inventory (fast path, no LLM)."""
from __future__ import annotations

import re
from datetime import date

from apps.inventory.room_availability import rooms_free_on_date
from apps.rfp_debate.models import RFPSubmission

from .client_group_context import (
    persist_group_size_to_intake,
    resolve_peak_rooms,
    resolve_stored_headcount,
)
from .client_session_memory import normalize_session
from .voice_card_updates import VoiceDateValidationError, parse_voice_card_patch
from .voice_intake_gates import availability_window
from .voice_prompts import compose_room_block_capacity_reply


def message_signals_room_block_sizing(message: str) -> bool:
    lower = (message or "").lower()
    if not lower.strip():
        return False
    if re.search(r"\b(one|solo|single|own|private)\s+rooms?\b", lower):
        return True
    if re.search(r"\bsolar\s+rooms?\b", lower):  # common ASR for "solo room"
        return True
    if re.search(r"\broom\s+per\s+(guest|person|participant|each)\b", lower):
        return True
    if re.search(r"\beach\s+(one|guest|person|participant)\b.*\broom", lower):
        return True
    if re.search(r"\b(\d+|a|one|two|hundred)\s*rooms?\b", lower):
        return True
    if re.search(r"\b(total\s+)?(a\s+)?hundred\s+rooms?\b", lower):
        return True
    if re.search(r"\b(\d+|hundred)\s*(need|needs)\s*(\d+|hundred)\s*rooms?\b", lower):
        return True
    if re.search(r"\bseveral rooms?\b|\bmultiple rooms?\b|\bnot one room\b", lower):
        return True
    if re.search(r"\b(one|solo)\s+room\s+per\b", lower):
        return True
    return False


def resolve_check_in_for_inventory(rfp: RFPSubmission) -> date | None:
    cards = rfp.active_ui_cards_json or {}
    overview = cards.get("event_overview") or {}
    for key in ("check_in_date",):
        raw = (overview.get(key) or "").strip()
        if raw and raw.upper() != "TBD":
            try:
                return date.fromisoformat(raw[:10])
            except ValueError:
                pass
    session = normalize_session(rfp.client_session_json)
    intake = session.get("intake") if isinstance(session.get("intake"), dict) else {}
    pending = (intake.get("check_in_iso") or "").strip()
    if pending:
        try:
            return date.fromisoformat(pending[:10])
        except ValueError:
            pass
    window_start, _ = availability_window(session)
    return window_start


def _apply_sizing_patch(rfp: RFPSubmission, message: str) -> dict | None:
    session = normalize_session(rfp.client_session_json)
    window_start, window_days = availability_window(session)
    try:
        patch = parse_voice_card_patch(
            message,
            availability_window_start=window_start,
            availability_window_days=window_days,
        )
    except VoiceDateValidationError:
        raise
    if not patch:
        return None
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(str(rfp.id), patch)
    rfp.refresh_from_db()
    return patch


def try_room_block_capacity_reply(rfp: RFPSubmission | None, message: str) -> str | None:
    """
    When the client sizes a peak room block, compare to inventory on the best-known check-in.
    Returns spoken guidance when the block exceeds free rooms, or a sizing ack with inventory note.
    """
    if not rfp:
        return None
    cleaned = (message or "").strip()
    if not cleaned:
        return None
    if not message_signals_room_block_sizing(cleaned):
        return None

    from .client_group_context import ensure_group_size_on_cards

    ensure_group_size_on_cards(rfp)

    try:
        _apply_sizing_patch(rfp, cleaned)
    except VoiceDateValidationError as exc:
        return exc.message

    headcount = resolve_stored_headcount(rfp)
    peak = resolve_peak_rooms(rfp, headcount=headcount) or headcount
    if not peak or peak <= 0:
        return None

    if headcount:
        persist_group_size_to_intake(rfp, headcount=headcount, peak_rooms=peak)

    check_in = resolve_check_in_for_inventory(rfp)
    if not check_in:
        return compose_room_block_capacity_reply(
            headcount=headcount,
            peak_rooms=peak,
            rooms_free=None,
            check_in_label=None,
        )

    free = rooms_free_on_date(check_in)
    label = check_in.strftime("%A, %B %d")
    if free is not None and peak > free:
        return compose_room_block_capacity_reply(
            headcount=headcount,
            peak_rooms=peak,
            rooms_free=free,
            check_in_label=label,
        )

    if free is not None:
        return compose_room_block_capacity_reply(
            headcount=headcount,
            peak_rooms=peak,
            rooms_free=free,
            check_in_label=label,
            fits=True,
        )
    return compose_room_block_capacity_reply(
        headcount=headcount,
        peak_rooms=peak,
        rooms_free=None,
        check_in_label=label,
    )
