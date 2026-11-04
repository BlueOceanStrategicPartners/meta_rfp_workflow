"""What is being priced: guest rooms + one meeting space, built from the RFP cards.

Both pricing engines (XGBoost and the rule fallback) start from the same PackageBase, so
retraining the model changes the demand multiplier, never the scale of the price.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg

from apps.inventory.models import (
    TRAINABLE_OCCUPANCY_SOURCES,
    HistoricalOccupancy,
    SpaceInventory,
    SpaceType,
    VenueProperty,
)

from .models import PricingPolicy

CENT = Decimal("0.01")
DEFAULT_ROOM_RATE = Decimal("200")
DEFAULT_SEATING_STYLE = "classroom"


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


class QuoteNotPossibleError(Exception):
    """The request cannot be priced as it stands (e.g. no space fits). Never priced silently."""

    def __init__(self, message: str, *, reason: str, alternatives: list[dict] | None = None):
        super().__init__(message)
        self.reason = reason
        self.alternatives = alternatives or []


@dataclass
class PackageBase:
    check_in: date | None
    check_out: date | None
    nights: int
    dates_assumed: bool
    room_nights: int
    peak_rooms_per_night: int
    room_rate: Decimal
    room_unit_cost: Decimal
    rooms_part: Decimal
    space: SpaceInventory | None
    event_days: int
    space_rate: Decimal
    space_part: Decimal
    base_price: Decimal
    operating_cost: Decimal
    headcount: int
    seating_style: str
    warnings: list[str] = field(default_factory=list)

    @property
    def stay_dates(self) -> list[date]:
        if not self.check_in:
            return []
        return [self.check_in + timedelta(days=i) for i in range(self.nights)]

    def as_inputs(self) -> dict:
        return {
            "check_in": self.check_in.isoformat() if self.check_in else None,
            "check_out": self.check_out.isoformat() if self.check_out else None,
            "nights": self.nights,
            "dates_assumed": self.dates_assumed,
            "room_nights": self.room_nights,
            "peak_rooms_per_night": self.peak_rooms_per_night,
            "room_rate": str(self.room_rate),
            "rooms_part": str(self.rooms_part),
            "space_id": str(self.space.id) if self.space else None,
            "space_name": self.space.name if self.space else None,
            "event_days": self.event_days,
            "space_rate": str(self.space_rate),
            "space_part": str(self.space_part),
            "base_price": str(self.base_price),
            "operating_cost": str(self.operating_cost),
            "headcount": self.headcount,
            "seating_style": self.seating_style,
            "warnings": list(self.warnings),
        }


def _parse_date(value) -> date | None:
    text = str(value or "").strip()
    if not text or text.upper() == "TBD":
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _int(value) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _nightly_rooms(room_block: dict) -> list[int]:
    nightly = []
    for block in room_block.get("blocks") or []:
        if isinstance(block, dict):
            nightly.append(sum(_int(block.get(k)) for k in ("single", "double", "deluxe", "suite")))
    return nightly


def _capacity(space: SpaceInventory, style: str) -> int:
    caps = space.capacities_json or {}
    return _int(caps.get(style) or caps.get(DEFAULT_SEATING_STYLE))


def _alternatives(spaces: list[SpaceInventory], style: str) -> list[dict]:
    ranked = sorted(spaces, key=lambda s: _capacity(s, style), reverse=True)[:3]
    return [{"id": str(s.id), "name": s.name, "capacity": _capacity(s, style)} for s in ranked]


def _choose_space(
    prop: VenueProperty, meeting: dict, headcount: int, style: str, warnings: list[str]
) -> SpaceInventory | None:
    spaces = list(SpaceInventory.objects.filter(property=prop).exclude(space_type=SpaceType.ROOM_BLOCK))
    if not spaces:
        # Inventory not set up yet: price the rooms and say so, rather than inventing a hall price.
        if headcount:
            warnings.append("No meeting spaces are set up in Inventory, so the meeting space isn't priced.")
        return None
    selected_id = meeting.get("selected_zone_id") or meeting.get("selected_space_id")
    if selected_id:
        space = next((s for s in spaces if str(s.id) == str(selected_id)), None)
        if space is None:
            raise QuoteNotPossibleError("The selected meeting space no longer exists.", reason="space_missing")
        if headcount and _capacity(space, style) < headcount:
            raise QuoteNotPossibleError(
                f"{space.name} seats {_capacity(space, style)} in {style} style, not {headcount}.",
                reason="space_too_small",
                alternatives=_alternatives(spaces, style),
            )
        return space
    if not headcount:
        return None  # rooms-only request: nothing to seat
    fitting = [s for s in spaces if _capacity(s, style) >= headcount]
    if not fitting:
        raise QuoteNotPossibleError(
            f"No single space fits {headcount} guests in {style} style.",
            reason="no_space_fits",
            alternatives=_alternatives(spaces, style),
        )
    return min(fitting, key=lambda s: (_capacity(s, style), s.rack_rate))


def _room_rate_and_cost(prop: VenueProperty, policy: PricingPolicy) -> tuple[Decimal, Decimal]:
    blocks = SpaceInventory.objects.filter(property=prop, space_type=SpaceType.ROOM_BLOCK, rack_rate__gt=0)
    if blocks.exists():
        agg = blocks.aggregate(rate=Avg("rack_rate"), cost=Avg("base_floor_cost"))
        rate = money(agg["rate"])
        cost = money(agg["cost"]) if agg["cost"] else money(rate * Decimal(str(policy.room_cost_pct)))
        return rate, cost
    adr = (
        HistoricalOccupancy.objects.filter(
            property=prop, source__in=TRAINABLE_OCCUPANCY_SOURCES, target_date__lt=date.today(), adr__gt=0
        ).aggregate(v=Avg("adr"))["v"]
    )
    rate = money(adr) if adr else DEFAULT_ROOM_RATE
    return rate, money(rate * Decimal(str(policy.room_cost_pct)))


def build_package(cards: dict, prop: VenueProperty, policy: PricingPolicy) -> PackageBase:
    overview = cards.get("event_overview") or {}
    meeting = cards.get("meeting_space") or {}
    room_block = cards.get("room_block") or {}
    warnings: list[str] = []

    check_in = _parse_date(overview.get("check_in_date"))
    check_out = _parse_date(overview.get("check_out_date"))
    nightly = [n for n in _nightly_rooms(room_block)]
    if any(nightly):
        room_nights, peak = sum(nightly), max(nightly)
    else:
        room_nights = _int(room_block.get("total_room_nights"))
        peak = 0  # set once nights are known

    if check_in and check_out:
        if check_out <= check_in:
            raise QuoteNotPossibleError("Check-out must be after check-in.", reason="invalid_dates")
        nights, dates_assumed = (check_out - check_in).days, False
    else:
        dates_assumed = True
        nights = len(nightly) if any(nightly) else 1
        if check_in and not check_out:
            check_out = check_in + timedelta(days=nights)
    if not any(nightly):
        peak = math.ceil(room_nights / nights) if room_nights else 0

    if peak > prop.total_rooms:
        warnings.append(f"Needs {peak} rooms a night but the hotel has {prop.total_rooms}.")

    headcount = _int(meeting.get("headcount"))
    style = str(meeting.get("seating_style") or DEFAULT_SEATING_STYLE).strip().lower()
    space = _choose_space(prop, meeting, headcount, style, warnings)
    event_days = max(1, nights)

    space_rate = money(space.rack_rate) if space else Decimal("0.00")
    if space is not None and space_rate <= 0:
        raise QuoteNotPossibleError(f"{space.name} has no price set in Inventory.", reason="missing_price")

    room_rate, room_cost = _room_rate_and_cost(prop, policy) if room_nights else (Decimal("0.00"), Decimal("0.00"))
    rooms_part = money(room_rate * room_nights)
    space_part = money(space_rate * event_days)
    base = money(rooms_part + space_part)
    if base <= 0:
        raise QuoteNotPossibleError("There is nothing to price yet: no rooms and no meeting space.", reason="nothing_to_price")
    space_cost = money(space.base_floor_cost) if space else Decimal("0.00")
    operating_cost = money(room_cost * room_nights + space_cost * event_days)

    return PackageBase(
        check_in=check_in,
        check_out=check_out,
        nights=nights,
        dates_assumed=dates_assumed,
        room_nights=room_nights,
        peak_rooms_per_night=peak,
        room_rate=room_rate,
        room_unit_cost=room_cost,
        rooms_part=rooms_part,
        space=space,
        event_days=event_days,
        space_rate=space_rate,
        space_part=space_part,
        base_price=base,
        operating_cost=operating_cost,
        headcount=headcount,
        seating_style=style,
        warnings=warnings,
    )
