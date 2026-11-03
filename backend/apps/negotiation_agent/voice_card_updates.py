"""Apply spoken corrections to RFP UI cards (headcount, room nights)."""
from __future__ import annotations

import re
from datetime import date

from .voice_dates import parse_arrival_date_from_voice, parse_stay_dates_from_voice, validate_stay_not_in_past


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
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
    }
    t = token.strip().lower()
    if t.isdigit():
        return int(t)
    return words.get(t)


def _numbers_in_text(lower: str) -> list[int]:
    out: list[int] = []
    for m in re.finditer(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|hundred)\b",
        lower,
    ):
        n = _word_to_int(m.group(1))
        if n is not None:
            out.append(n)
    hv = _hundred_phrase_value(lower)
    if hv is not None:
        out.append(hv)
    return out


def _hundred_phrase_value(lower: str) -> int | None:
    if re.search(r"\b(a|one)\s+hundred\b", lower):
        return 100
    m = re.search(r"\b(\d+)\s+hundred\b", lower)
    if m:
        return int(m.group(1)) * 100
    if re.search(r"\bhundred\b", lower):
        return 100
    return None


def _peak_rooms_from_message(lower: str) -> int | None:
    need_m = re.search(r"\b(\d+|hundred)\s*need\s*(\d+|hundred)\s*rooms?\b", lower)
    if need_m:
        n2 = _word_to_int(need_m.group(2)) or _hundred_phrase_value(f"x {need_m.group(2)}")
        if n2:
            return n2
    if re.search(r"\b(total\s+)?(a\s+)?hundred\s+rooms?\b", lower):
        return 100
    hv = _hundred_phrase_value(lower)
    if hv and re.search(r"\brooms?\b", lower):
        return hv
    room_counts = [int(m.group(1)) for m in re.finditer(r"\b(\d+)\s*rooms?\b", lower)]
    if room_counts:
        return max(room_counts)
    one_per = re.search(
        r"\b(one|solo|single|solar)\s+room\b|\bone\s+room\s+per\b|\beach\s+(one|guest|person)\b.*\broom",
        lower,
    )
    if one_per:
        hc = _group_size_from_message(lower)
        if hc:
            return hc
        nums = _numbers_in_text(lower)
        if nums:
            return max(nums)
    rooms_m = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|hundred)\s*rooms?\b",
        lower,
    )
    if rooms_m:
        n = _word_to_int(rooms_m.group(1))
        if n and n > 1:
            return n
    return None


def _group_size_from_message(lower: str) -> int | None:
    if re.search(r"\b(a|one)\s+hundred\s+(gates|guests|people|attendees|pax|participants?)\b", lower):
        return 100
    if re.search(r"\bhundred\s+(gates|guests|people|attendees|pax|participants?)\b", lower):
        return 100
    part_m = re.search(r"\b(\d+)\s*participants?\b", lower)
    if part_m:
        return int(part_m.group(1))
    if re.search(r"\bheadcount\b", lower) and "not" in lower:
        nums = _numbers_in_text(lower)
        trail = re.search(r"\b(?:it'?s?|is)\s*(\d+|twenty|thirty|forty|fifty)\s*$", lower)
        if trail:
            v = _word_to_int(trail.group(1))
            if v:
                return v
        if len(nums) >= 2:
            return nums[-1]
    if any(w in lower for w in ("headcount", "guest", "people", "attendee", "pax", "participant")):
        nums = _numbers_in_text(lower)
        if nums:
            if "not" in lower and len(nums) >= 2:
                return nums[-1]
            return max(nums)
    return None


def parse_voice_card_patch(
    message: str,
    *,
    availability_window_start: date | None = None,
    availability_window_days: int = 7,
) -> dict | None:
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
    else:
        arrival = parse_arrival_date_from_voice(
            cleaned,
            availability_window_start=availability_window_start,
            availability_window_days=availability_window_days,
        )
        if arrival is not None:
            err = validate_stay_not_in_past(arrival, arrival)
            if err:
                raise VoiceDateValidationError(err)
            patch["event_overview"] = {"check_in_date": arrival.isoformat()}

    peak = _peak_rooms_from_message(lower)
    if peak and peak > 0:
        patch.setdefault("room_block", {})["peak_rooms"] = peak

    headcount = _group_size_from_message(lower)
    if headcount and headcount > 0:
        patch["meeting_space"] = {"headcount": headcount}
        if peak is None and re.search(
            r"\b(one|solo|single|solar)\s+room\b|\bper\s+guest\b|\bper\s+person\b|one participant needs one room|each one",
            lower,
        ):
            patch.setdefault("room_block", {})["peak_rooms"] = headcount

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
