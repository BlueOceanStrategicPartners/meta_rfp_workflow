"""Apply spoken corrections to RFP UI cards (headcount, room nights)."""
from __future__ import annotations

import re
from datetime import date

from .voice_dates import parse_stay_dates_from_voice, validate_stay_not_in_past


class VoiceDateValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _word_to_int(token: str) -> int | None:
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "fifteen": 15,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
    }
    t = token.strip().lower()
    if t.isdigit():
        return int(t)
    return words.get(t)


def _numbers_in_text(lower: str) -> list[int]:
    out: list[int] = []
    for m in re.finditer(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty)\b",
        lower,
    ):
        n = _word_to_int(m.group(1))
        if n is not None:
            out.append(n)
    return out


def parse_voice_card_patch(message: str) -> dict | None:
    """Return partial card payload to merge, or None if no structured update detected."""
    cleaned = message.strip()
    if not cleaned:
        return None
    lower = cleaned.lower()
    patch: dict = {}

    stay = parse_stay_dates_from_voice(cleaned)
    if stay:
        check_in, check_out = stay
        err = validate_stay_not_in_past(check_in, check_out)
        if err:
            raise VoiceDateValidationError(err)
        nights = max(1, (check_out - check_in).days)
        patch["event_overview"] = {
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        }
        patch.setdefault("room_block", {})["total_room_nights"] = nights

    rooms_m = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*rooms?\b",
        lower,
    )
    if rooms_m:
        n = _word_to_int(rooms_m.group(1))
        if n and n > 0:
            patch.setdefault("room_block", {})["peak_rooms"] = n

    if any(w in lower for w in ("headcount", "guest", "people", "attendee", "pax")):
        nums = _numbers_in_text(lower)
        headcount: int | None = None
        if nums and any(w in lower for w in ("not", "actually", "correction", "wrong", "instead")):
            headcount = nums[-1]
        elif nums:
            headcount = nums[-1]
        # Prefer explicit trailing value: "not 50, it is 20"
        trail = re.search(r"\b(?:it'?s?|is)\s*(\d+|twenty|thirty|forty|fifty)\s*$", lower)
        if trail:
            headcount = _word_to_int(trail.group(1))
        elif re.search(r"\bheadcount\b", lower):
            m = re.search(
                r"\bheadcount\b.*?\b(\d+|twenty|thirty|forty|fifty)\s*$",
                lower,
            )
            if m:
                headcount = _word_to_int(m.group(1))
        if headcount is not None and headcount > 0:
            patch["meeting_space"] = {"headcount": headcount}

    if re.search(r"\bnights?\b", lower):
        nums = _numbers_in_text(lower)
        nights: int | None = None
        if nums and "not" in lower and "headcount" not in lower:
            nights = nums[-1]
        else:
            m = re.search(
                r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b",
                lower,
            )
            if m:
                nights = _word_to_int(m.group(1))
        if nights is not None and nights > 0:
            patch.setdefault("room_block", {})["total_room_nights"] = nights

    return patch or None


def apply_voice_message_to_cards(session_id: str, message: str) -> dict | None:
    """Persist voice corrections and re-price. Returns patch applied or None."""
    try:
        patch = parse_voice_card_patch(message)
    except VoiceDateValidationError:
        raise
    if not patch:
        return None
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(session_id, patch)
    return patch
