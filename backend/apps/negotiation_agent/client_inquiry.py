"""Answer planning questions — group size, room types, next-week inventory in one turn."""
from __future__ import annotations

import re
from typing import Any

from apps.inventory.room_availability import (
    build_availability_table,
    spoken_availability_for_message,
    spoken_availability_intro,
)
from apps.rfp_debate.models import RFPSubmission

from .voice_dates import parse_weekday_index
from .voice_card_updates import VoiceDateValidationError, parse_room_nights_from_block_phrase, parse_voice_card_patch
from .voice_intake import record_availability_window
from .client_group_context import (
    message_sets_new_headcount,
    participant_count_from_message,
    persist_group_size_to_intake,
    resolve_stored_headcount,
)

ROOM_CATALOG_SPOKEN = (
    "Our guest inventory is mainly standard king and double-queen rooms, plus executive-floor kings "
    "and a small suite tier for VIPs — all eligible for the same group concessions when you block together."
)


def _participant_count(message: str) -> int | None:
    return participant_count_from_message(message)


def detect_room_catalog_question(message: str) -> bool:
    lower = (message or "").lower()
    patterns = (
        r"\bwhat kind of rooms?\b",
        r"\bwhat type of rooms?\b",
        r"\bwhat rooms?\b",
        r"\bwhat do you offer\b",
        r"\bhow about your rooms?\b",
        r"\broom types?\b",
        r"\btell me about (?:your )?rooms\b",
    )
    return any(re.search(p, lower) for p in patterns)


def _is_arrival_preference_only(message: str) -> bool:
    """Weekday + arrive/come — handled by intake gates, not generic next-week planning."""
    lower = (message or "").lower()
    if parse_weekday_index(message) is None:
        return False
    if not re.search(r"\barriv|\bcome|\bcheck[\s-]?in|\bvisit|\bhost\b", lower):
        return False
    if _participant_count(message) or detect_room_catalog_question(message):
        return False
    return True


def detect_planning_turn(message: str) -> bool:
    lower = (message or "").lower()
    if not lower.strip():
        return False
    if _is_arrival_preference_only(message):
        return False
    if "next week" in lower:
        return True
    if detect_room_catalog_question(message):
        return True
    if _participant_count(message):
        return True
    if re.search(r"\bseveral rooms?\b|\bmultiple rooms?\b|\bnot one room\b", lower):
        return True
    if re.search(r"\bhow about your rooms?\b", lower):
        return True
    return False


def _apply_planning_patch(rfp: RFPSubmission, message: str) -> dict[str, Any] | None:
    try:
        patch = parse_voice_card_patch(message)
    except VoiceDateValidationError:
        raise

    lower = message.lower()
    participants = _participant_count(message)
    if participants and not (patch or {}).get("meeting_space", {}).get("headcount"):
        patch = patch or {}
        patch["meeting_space"] = {"headcount": participants}

    if not (patch or {}).get("room_block", {}).get("total_room_nights"):
        n = parse_room_nights_from_block_phrase(message)
        if n and n > 0:
            patch = patch or {}
            patch.setdefault("room_block", {})["total_room_nights"] = n

    if re.search(r"\bseveral rooms?\b|\bmultiple rooms?\b|\bnot one room\b", lower):
        peak = participants
        if patch:
            peak = peak or (patch.get("room_block") or {}).get("peak_rooms")
            meeting = patch.get("meeting_space") or {}
            peak = peak or meeting.get("headcount")
        if peak:
            patch = patch or {}
            patch.setdefault("room_block", {})["peak_rooms"] = int(peak)

    if not patch:
        return None
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(str(rfp.id), patch)
    rfp.refresh_from_db()
    return patch


def try_client_planning_response(
    rfp: RFPSubmission | None,
    message: str,
) -> tuple[str, dict[str, Any] | None] | None:
    """
    One spoken answer for “next week + 100 participants + what rooms do you have?” style turns.
    Returns (spoken, ui_component) or None.
    """
    if not rfp or not detect_planning_turn(message):
        return None

    try:
        _apply_planning_patch(rfp, message)
    except VoiceDateValidationError as exc:
        return exc.message, None

    cards = rfp.active_ui_cards_json or {}
    meeting = cards.get("meeting_space") or {}
    room = cards.get("room_block") or {}
    try:
        headcount = int(meeting.get("headcount") or 0)
    except (TypeError, ValueError):
        headcount = 0
    try:
        peak = int(room.get("peak_rooms") or 0)
    except (TypeError, ValueError):
        peak = 0

    parts: list[str] = []
    lower = message.lower()

    if headcount > 0:
        block_hint = peak or headcount
        persist_group_size_to_intake(rfp, headcount=headcount, peak_rooms=block_hint)
        parts.append(
            f"I've logged about {headcount} participants on your summary cards — "
            f"for a one-room-per-guest block that's roughly {block_hint} guest rooms at peak."
        )
    elif re.search(r"\bseveral rooms?\b|\bmultiple rooms?\b", lower):
        parts.append(
            "Got it — you're looking at a multi-room block rather than a single room. "
            "Share your participant count and I'll size the peak rooms on the cards."
        )

    if detect_room_catalog_question(message) or re.search(r"\bhow about your rooms?\b", lower):
        parts.append(ROOM_CATALOG_SPOKEN)

    ui: dict[str, Any] | None = None
    if "next week" in lower:
        table = build_availability_table()
        if table.get("rows"):
            record_availability_window(rfp, table)
            ui = table
            parts.append(spoken_availability_for_message(table, message))
            if headcount > 0 and table.get("rows"):
                best_free = max(int(r.get("rooms_available") or 0) for r in table["rows"])
                if headcount > best_free:
                    parts.append(
                        f"Your {headcount}-guest block is above the best single-day free count "
                        f"({best_free} rooms) next week — tell me if you'd like doubles or a split pattern."
                    )
            stored = resolve_stored_headcount(rfp)
            if stored and not message_sets_new_headcount(message):
                parts.append(
                    "Should I proceed with that participant count, or do you want to change it?"
                )
            parts.append("How many nights should I hold for the group?")
        else:
            parts.append(
                "I don't have live counts for next week loaded yet — tell me arrival day and nights "
                "and I'll verify the block."
            )
    elif detect_room_catalog_question(message) and "next week" not in lower:
        parts.append("Tell me your arrival week or say next week and I'll pull live room counts.")

    if not parts:
        return None
    return " ".join(parts), ui
