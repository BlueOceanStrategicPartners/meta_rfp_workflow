"""Voice stay dates — resolve ordinals against today, reject past check-in."""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from django.utils import timezone


def voice_today() -> date:
    return timezone.localdate()


def voice_date_context_line() -> str:
    today = voice_today()
    return (
        f"Today is {today.isoformat()} ({today.strftime('%A, %B %d, %Y')}). "
        "When the client names a weekday or taps a date from the availability table, treat it as their "
        "arrival preference — resolve to a concrete calendar date, confirm briefly, then ask only for "
        "what is still missing (usually number of nights or headcount). Do not ask again for a "
        "'future date' they already gave. Reject check-in before today."
    )


_WEEKDAY_NAMES: dict[str, int] = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


def parse_weekday_index(message: str) -> int | None:
    lower = (message or "").lower()
    for name, idx in sorted(_WEEKDAY_NAMES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(name)}\b", lower):
            return idx
    return None


def next_on_or_after_weekday(weekday: int, ref: date | None = None) -> date:
    ref = ref or voice_today()
    cursor = ref
    for _ in range(8):
        if cursor.weekday() == weekday:
            return cursor
        cursor += timedelta(days=1)
    return ref + timedelta(days=(weekday - ref.weekday()) % 7)


def resolve_weekday_in_window(weekday: int, window_start: date, days: int = 7) -> date | None:
    for i in range(max(1, days)):
        candidate = window_start + timedelta(days=i)
        if candidate.weekday() == weekday:
            return candidate
    return None


_MONTH_NAMES: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def parse_calendar_date_phrase(message: str, *, ref: date | None = None) -> date | None:
    """Parse 'Nov 10', 'November 10', or ISO fragments in speech."""
    ref = ref or voice_today()
    lower = (message or "").lower()
    iso_m = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", lower)
    if iso_m:
        try:
            return date.fromisoformat(iso_m.group(1))
        except ValueError:
            pass
    for month_token, month_num in sorted(_MONTH_NAMES.items(), key=lambda x: -len(x[0])):
        m = re.search(rf"\b{re.escape(month_token)}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", lower)
        if m:
            day = int(m.group(1))
            year = ref.year
            candidate = _resolve_day_in_month(day, year, month_num)
            if candidate < ref and month_num < ref.month:
                candidate = _resolve_day_in_month(day, year + 1, month_num)
            elif candidate < ref:
                candidate = _resolve_day_in_month(day, year + 1, month_num)
            return candidate
    return None


def parse_arrival_date_from_voice(
    message: str,
    *,
    availability_window_start: date | None = None,
    availability_window_days: int = 7,
    ref: date | None = None,
) -> date | None:
    """Best-effort arrival date from weekday names, month/day phrases, or ISO."""
    ref = ref or voice_today()
    explicit = parse_calendar_date_phrase(message, ref=ref)
    if explicit is not None:
        return explicit
    lower = (message or "").lower()
    weekday = parse_weekday_index(message)
    if weekday is not None and re.search(r"\bnext week\b", lower):
        from apps.inventory.room_availability import next_calendar_week_range

        start, end = next_calendar_week_range(ref=ref)
        in_window = resolve_weekday_in_window(weekday, start, (end - start).days + 1)
        if in_window is not None:
            return in_window
    if weekday is None:
        return None
    if availability_window_start is not None:
        in_window = resolve_weekday_in_window(
            weekday, availability_window_start, availability_window_days
        )
        if in_window is not None:
            return in_window
    return next_on_or_after_weekday(weekday, ref)


def _resolve_day_in_month(day: int, year: int, month: int) -> date:
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def next_future_date(day: int, ref: date | None = None) -> date:
    """Next calendar date with this day-of-month on or after ref (default today)."""
    ref = ref or voice_today()
    month = ref.month
    year = ref.year
    for _ in range(14):
        candidate = _resolve_day_in_month(day, year, month)
        if candidate >= ref:
            return candidate
        month += 1
        if month > 12:
            month = 1
            year += 1
    return _resolve_day_in_month(day, year, month)


def checkout_after_checkin(day: int, check_in: date) -> date:
    candidate = _resolve_day_in_month(day, check_in.year, check_in.month)
    if candidate > check_in:
        return candidate
    return _resolve_day_in_month(day, check_in.year, check_in.month + 1)


def parse_stay_dates_from_voice(message: str) -> tuple[date, date] | None:
    lower = message.lower()
    arrive_day: int | None = None
    depart_day: int | None = None

    m = re.search(
        r"\b(?:arriv(?:e|al|ing)|check[\s-]?in)\s*(?:on|the|by)?\s*(\d{1,2})(?:st|nd|rd|th)?\b",
        lower,
    )
    if m:
        arrive_day = int(m.group(1))

    m = re.search(
        r"\b(?:depart(?:ure|ing)|leave|check[\s-]?out)\s*(?:on|will be|the|by)?\s*(\d{1,2})(?:st|nd|rd|th)?\b",
        lower,
    )
    if m:
        depart_day = int(m.group(1))

    ordinals = [int(x.group(1)) for x in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)\b", lower)]
    if arrive_day is None and ordinals:
        arrive_day = ordinals[0]
    if depart_day is None and len(ordinals) >= 2:
        depart_day = ordinals[1]

    if arrive_day is None or depart_day is None:
        return None

    check_in = next_future_date(arrive_day)
    check_out = checkout_after_checkin(depart_day, check_in)
    if check_out <= check_in:
        check_out = check_in + timedelta(days=max(1, depart_day - arrive_day))
    return check_in, check_out


def validate_stay_not_in_past(check_in: date, check_out: date) -> str | None:
    today = voice_today()
    if check_in < today:
        return (
            f"That check-in is in the past — today is {today.strftime('%B %d, %Y')}. "
            "Please give an arrival date on or after today."
        )
    if check_out < check_in:
        return "Check-out needs to be after check-in. Can you confirm both dates again?"
    return None
