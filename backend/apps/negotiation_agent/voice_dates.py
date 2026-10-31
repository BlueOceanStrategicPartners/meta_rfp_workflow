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
        "Do not confirm or quote stays with check-in before today; ask for a future date if unclear."
    )


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
