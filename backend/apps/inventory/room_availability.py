"""Guest-room availability windows from HistoricalOccupancy + meeting-space inventory."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from apps.inventory.models import HistoricalOccupancy, SpaceInventory, VenueProperty

# Demo hotel capacity — occupancy rows are property-level.
DEFAULT_ROOM_COUNT = 320
DEFAULT_OCCUPANCY = 0.62


def default_property() -> VenueProperty | None:
    return VenueProperty.objects.order_by("created_at").first()


def detect_availability_inquiry(message: str) -> bool:
    lower = (message or "").lower()
    if not lower.strip():
        return False
    patterns = (
        r"\bnext week\b",
        r"\bthis week\b",
        r"\bcoming week\b",
        r"\bsuitable date",
        r"\bwhat date",
        r"\bwhich date",
        r"\bwhen can we\b",
        r"\bwhen could we\b",
        r"\bvisit (?:your |the )?(?:property|hotel|venue)\b",
        r"\bcome to (?:your |the )?(?:property|hotel)\b",
        r"\broom availability\b",
        r"\bfree slot",
        r"\bavailability\b.*\broom",
        r"\bneed(?:ing)?\s+(?:a\s+)?rooms?\b.*\bnext week\b",
        r"\bnext week\b.*\brooms?\b",
        r"\bwhat kind of rooms?\b",
        r"\bhow about your rooms?\b",
    )
    return any(re.search(p, lower) for p in patterns)


def next_calendar_week_range(*, ref: date | None = None) -> tuple[date, date]:
    """Monday–Sunday of the week after the week containing ref."""
    ref = ref or timezone.localdate()
    # Start of next week (Monday after current week ends)
    days_until_next_monday = (7 - ref.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7
    start = ref + timedelta(days=days_until_next_monday)
    end = start + timedelta(days=6)
    return start, end


def _status_label(occupancy_pct: float) -> str:
    if occupancy_pct < 0.72:
        return "Good"
    if occupancy_pct < 0.88:
        return "Limited"
    return "Tight"


def _meeting_space_summary(property_id) -> str:
    spaces = SpaceInventory.objects.filter(property_id=property_id, is_booked=False)
    names = [s.name for s in spaces[:3]]
    if not names:
        return "On request"
    if len(names) == 1:
        return names[0]
    return f"{names[0]} + {len(names) - 1} more"


def ensure_occupancy_rows(property: VenueProperty, start: date, days: int) -> None:
    """Fill missing occupancy rows for demo queries (does not overwrite existing)."""
    for i in range(days):
        target = start + timedelta(days=i)
        if HistoricalOccupancy.objects.filter(property=property, target_date=target).exists():
            continue
        # Gentle weekly curve for plausible demo slots
        occ = 0.58 + (target.weekday() / 10.0) + (i % 3) * 0.05
        occ = min(0.92, max(0.45, occ))
        HistoricalOccupancy.objects.create(
            property=property,
            target_date=target,
            room_occupancy_pct=occ,
            hall_utilization_pct=min(0.85, occ + 0.08),
            adr=215,
            revpar=int(215 * occ),
        )


def build_availability_table(
    *,
    property: VenueProperty | None = None,
    start: date | None = None,
    days: int = 7,
) -> dict[str, Any]:
    prop = property or default_property()
    if not prop:
        return {
            "title": "Room availability",
            "caption": "No venue inventory is configured yet.",
            "columns": [],
            "rows": [],
        }

    if start is None:
        start, _ = next_calendar_week_range()

    ensure_occupancy_rows(prop, start, days)
    meeting = _meeting_space_summary(prop.id)

    rows: list[dict[str, Any]] = []
    for i in range(days):
        target = start + timedelta(days=i)
        occ_row = HistoricalOccupancy.objects.filter(property=prop, target_date=target).first()
        occ = float(occ_row.room_occupancy_pct) if occ_row else DEFAULT_OCCUPANCY
        free_rooms = max(0, int(DEFAULT_ROOM_COUNT * (1.0 - occ)))
        rows.append(
            {
                "date_iso": target.isoformat(),
                "date_label": target.strftime("%a, %b %d"),
                "occupancy_pct": round(occ * 100),
                "rooms_available": free_rooms,
                "meeting_space": meeting,
                "status": _status_label(occ),
            }
        )

    good_dates = [r["date_label"] for r in rows if r["status"] == "Good"][:3]
    caption = (
        f"Next week at {prop.name} — tap a row to pick arrival."
        if good_dates
        else f"Next week at {prop.name} — limited inventory; tap the best fit."
    )

    return {
        "type": "availability_table",
        "title": f"{prop.name} — guest room windows",
        "caption": caption,
        "window_start_iso": start.isoformat(),
        "window_days": days,
        "columns": [
            {"key": "date_label", "label": "Date"},
            {"key": "rooms_available", "label": "Rooms free", "align": "right"},
            {"key": "occupancy_pct", "label": "Occupied %", "align": "right"},
            {"key": "meeting_space", "label": "Meeting space"},
            {"key": "status", "label": "Fit"},
        ],
        "rows": rows,
        "highlights": good_dates,
    }


def rooms_free_on_date(target: date, *, property: VenueProperty | None = None) -> int | None:
    prop = property or default_property()
    if not prop:
        return None
    ensure_occupancy_rows(prop, target, 1)
    occ_row = HistoricalOccupancy.objects.filter(property=prop, target_date=target).first()
    occ = float(occ_row.room_occupancy_pct) if occ_row else DEFAULT_OCCUPANCY
    return max(0, int(DEFAULT_ROOM_COUNT * (1.0 - occ)))


def inventory_capacity_warning(check_in: date, rooms_needed: int) -> str | None:
    if rooms_needed <= 0:
        return None
    free = rooms_free_on_date(check_in)
    if free is None or rooms_needed <= free:
        return None
    label = check_in.strftime("%A, %B %d")
    return (
        f"On {label} inventory shows about {free} rooms free — "
        f"below your {rooms_needed}-room peak. We can use doubles, reduce the block, or pick another date."
    )


def inventory_fits_block(check_in: date, rooms_needed: int) -> tuple[int | None, bool]:
    """Return (rooms_free, fits). fits is True when needed <= free or inventory unknown."""
    if rooms_needed <= 0:
        free = rooms_free_on_date(check_in)
        return free, True
    free = rooms_free_on_date(check_in)
    if free is None:
        return None, True
    return free, rooms_needed <= free


def spoken_availability_intro(table: dict[str, Any]) -> str:
    rows = table.get("rows") or []
    good = [r for r in rows if r.get("status") == "Good"]
    if good:
        best = good[0]
        return (
            f"I checked live inventory for next week. "
            f"{best['date_label']} looks strongest with about {best['rooms_available']} rooms free — "
            f"I've put the full week in a table you can tap."
        )
    if rows:
        r0 = rows[0]
        return (
            f"Next week is tighter, but {r0['date_label']} still has about {r0['rooms_available']} rooms — "
            f"see the table for the full picture."
        )
    return (
        "I couldn't load property availability right now. "
        "Tell me your preferred arrival day and I'll check again."
    )


def spoken_availability_for_message(table: dict[str, Any], message: str) -> str:
    """When the client names a weekday, answer for that day — not the generic 'best day' blurb."""
    from apps.negotiation_agent.voice_dates import parse_weekday_index

    weekday = parse_weekday_index(message)
    rows = table.get("rows") or []
    if weekday is None or not rows:
        return spoken_availability_intro(table)

    target_row = None
    for row in rows:
        iso = (row.get("date_iso") or "")[:10]
        if not iso:
            continue
        try:
            if date.fromisoformat(iso).weekday() == weekday:
                target_row = row
                break
        except ValueError:
            continue

    if not target_row:
        return spoken_availability_intro(table)

    free = int(target_row.get("rooms_available") or 0)
    label = target_row.get("date_label") or target_row.get("date_iso", "")
    status = (target_row.get("status") or "").strip()
    weekday_name = date.fromisoformat(str(target_row["date_iso"])[:10]).strftime("%A")

    msg = (
        f"For next week {weekday_name} — {label} — inventory shows about {free} rooms free."
    )
    if status and status != "Good":
        good = [r for r in rows if r.get("status") == "Good"]
        if good:
            alt = good[0]
            msg += (
                f" That's tighter than {alt.get('date_label')} ({alt.get('rooms_available')} rooms), "
                "but we can still work with your "
                f"{weekday_name} arrival."
            )
    msg += " I've put the full week in the table you can tap."
    return msg
