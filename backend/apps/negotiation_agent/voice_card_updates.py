"""Apply spoken corrections to RFP UI cards (headcount, room nights)."""
from __future__ import annotations

import re
from datetime import date, timedelta

from .voice_dates import (
    message_mentions_checkout,
    parse_arrival_date_from_voice,
    parse_duration_nights_from_voice,
    parse_stay_dates_from_voice,
    parse_stay_from_checkout_and_duration,
    validate_stay_not_in_past,
)


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


_SEATING_ALIASES: dict[str, str] = {
    "classroom": "classroom",
    "theater": "theater",
    "theatre": "theater",
    "banquet": "banquet",
    "u-shape": "u-shape",
    "u shape": "u-shape",
    "ushape": "u-shape",
    "boardroom": "boardroom",
    "board room": "boardroom",
    "hollow square": "u-shape",
    "cabaret": "banquet",
}


def parse_seating_style_from_voice(message: str) -> str | None:
    lower = (message or "").lower()
    if not re.search(r"\b(seating|style|setup|set up|layout)\b", lower) and not re.search(
        r"\b(classroom|theater|theatre|banquet|u-?shape|boardroom|cabaret)\b",
        lower,
    ):
        return None
    for phrase, canonical in sorted(_SEATING_ALIASES.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            return canonical
    return None


def _clause_around_keywords(message: str, keywords: tuple[str, ...]) -> str:
    cleaned = (message or "").strip()
    if not cleaned:
        return ""
    lower = cleaned.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx >= 0:
            start = max(0, cleaned.rfind(".", 0, idx) + 1, cleaned.rfind(",", 0, idx) + 1)
            end = len(cleaned)
            for sep in (".", "?", "!"):
                hit = cleaned.find(sep, idx)
                if hit >= 0:
                    end = min(end, hit)
            snippet = cleaned[start:end].strip(" ,.;")
            if len(snippet) >= 8:
                return snippet[:500]
    return cleaned[:500]


def parse_catering_av_from_voice(message: str) -> dict | None:
    """Return partial patch keys catering_av (+ meeting_space.av for proposal bindings)."""
    lower = (message or "").lower()
    catering: str | None = None
    av: str | None = None

    if re.search(
        r"\b(breakfast|lunch|dinner|catering|coffee|buffet|meal|brunch|reception|snack)\b",
        lower,
    ):
        catering = _clause_around_keywords(
            message,
            (
                "continental breakfast",
                "breakfast",
                "lunch",
                "dinner",
                "catering",
                "coffee",
                "buffet",
                "meal",
            ),
        )

    if re.search(
        r"\b(projector|projection|screen|av\b|audio.?visual|microphone|mic\b|speakers?|hdmi|sound system|pa system)\b",
        lower,
    ):
        av = _clause_around_keywords(
            message,
            (
                "projector",
                "projection",
                "screen",
                "audio visual",
                "av ",
                "microphone",
                "speaker",
            ),
        )

    if catering and av and catering.strip().lower() == av.strip().lower():
        parts = re.split(r"\s+and\s+", message, flags=re.I)
        if len(parts) >= 2:
            catering = parts[0].strip()[:500]
            av = parts[-1].strip()[:500]

    if not catering and not av:
        return None

    patch: dict = {"catering_av": {}}
    if catering:
        patch["catering_av"]["catering"] = catering
    if av:
        patch["catering_av"]["av"] = av
        patch["meeting_space"] = {"av": av}
    return patch


def parse_room_nights_from_block_phrase(message: str) -> int | None:
    """e.g. '3-night room block' or 'three nights room block'."""
    lower = (message or "").lower()
    m = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*[\-\s]?nights?\s*(?:room\s+)?block\b",
        lower,
    )
    if not m:
        return None
    return _word_to_int(m.group(1))


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
    if not stay:
        stay = parse_stay_from_checkout_and_duration(cleaned)
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
        duration_nights = parse_duration_nights_from_voice(cleaned)
        if message_mentions_checkout(cleaned):
            from .voice_dates import parse_checkout_date_from_voice, voice_today

            checkout = parse_checkout_date_from_voice(cleaned, ref=voice_today())
            if checkout is not None and duration_nights:
                check_in = checkout - timedelta(days=max(1, duration_nights))
                err = validate_stay_not_in_past(check_in, checkout)
                if err:
                    raise VoiceDateValidationError(err)
                patch["event_overview"] = {
                    "check_in_date": check_in.isoformat(),
                    "check_out_date": checkout.isoformat(),
                }
                patch.setdefault("room_block", {})["total_room_nights"] = max(1, duration_nights)
            elif checkout is not None:
                patch["event_overview"] = {"check_out_date": checkout.isoformat()}
        elif duration_nights is None:
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
        elif duration_nights and duration_nights > 0:
            patch.setdefault("room_block", {})["total_room_nights"] = duration_nights

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

    block_nights = parse_room_nights_from_block_phrase(cleaned)
    if block_nights and block_nights > 0:
        patch.setdefault("room_block", {})["total_room_nights"] = block_nights

    seating = parse_seating_style_from_voice(cleaned)
    if seating:
        patch.setdefault("meeting_space", {})["seating_style"] = seating

    catering_av = parse_catering_av_from_voice(cleaned)
    if catering_av:
        patch.setdefault("catering_av", {}).update(catering_av.get("catering_av") or {})
        if catering_av.get("meeting_space"):
            patch.setdefault("meeting_space", {}).update(catering_av["meeting_space"])

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
