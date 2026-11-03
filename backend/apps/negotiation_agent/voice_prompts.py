"""Prompt templates for client voice — classification, slot fill, spoken replies."""
from __future__ import annotations

INTAKE_CLASSIFIER_SYSTEM = """You classify one client voice turn for a hotel RFP assistant.
Return JSON only. Use session facts as authoritative; never re-ask for values already on record.

Fields:
- intent: social | set_group_size | set_arrival | set_nights | set_stay_complete | availability | other
- headcount: integer or null
- peak_rooms: integer or null
- check_in_iso: YYYY-MM-DD or null
- nights: integer or null
- confidence: 0.0-1.0
- reply: one or two short spoken sentences if confidence >= 0.85 else empty string

Rules:
- Do not quote prices unless stay has check-in, nights, and peak rooms confirmed.
- Do not ask meeting space or catering unless the client mentioned them.
- If group size is on record, confirm it instead of re-asking.
- Mention inventory only when peak_rooms exceeds rooms_free_on_check_in (when provided)."""

INTAKE_REPLY_SYSTEM = """You are a hospitality sales assistant on a voice call.
Use ONLY facts in CLIENT SESSION MEMORY. Warm, concise, one or two sentences.
Never mention AI, models, cards UI mechanics, venue maps, or floor prices.
Do not ask for headcount if group size is already on record.
Ask exactly ONE next question when a slot is missing (usually nights after arrival)."""


def intake_classifier_user(session_block: str, message: str, *, rooms_free: int | None = None) -> str:
    extra = f"\nRooms free on proposed check-in: {rooms_free}." if rooms_free is not None else ""
    return f"{session_block}{extra}\n\nClient said: {message}"


def compose_arrival_nights_reply(
    *,
    arrival_label: str,
    headcount: int | None,
    peak_rooms: int | None,
    inventory_note: str | None,
    permission_ask: bool,
    confirm_stored_group: bool,
    rooms_free: int | None = None,
    rooms_needed: int | None = None,
) -> str:
    needed = int(rooms_needed or peak_rooms or headcount or 0)
    over = rooms_free is not None and needed > 0 and needed > rooms_free

    if over:
        parts: list[str] = []
        if headcount and confirm_stored_group:
            parts.append(
                f"You mentioned {headcount} participants — I'll keep that on your block unless you'd like to change it."
            )
        elif headcount and peak_rooms:
            parts.append(
                f"I've noted {headcount} guests and a {peak_rooms}-room peak on your summary cards."
            )
        parts.append(
            f"For arrival {arrival_label}, we only have about {rooms_free} rooms free — "
            f"we can't hold {needed} single-occupancy rooms that night."
        )
        if inventory_note:
            parts.append(inventory_note)
        parts.append(
            "We could use doubles, reduce the block, or pick another date — what works best?"
        )
        return " ".join(p.strip() for p in parts if p.strip())

    parts = []
    if headcount and confirm_stored_group:
        parts.append(
            f"You mentioned {headcount} participants — I'll keep that on your block unless you'd like to change it."
        )
    elif headcount and peak_rooms:
        parts.append(
            f"I've noted {headcount} guests and a {peak_rooms}-room peak on your summary cards."
        )
    if permission_ask:
        parts.append(f"Yes — we can work toward arrival {arrival_label}.")
    else:
        parts.append(f"Got it — arrival on {arrival_label}.")
    if rooms_free is not None and needed > 0 and rooms_free >= needed:
        parts.append(
            f"Inventory that day shows about {rooms_free} rooms free, which covers your {needed}-room peak."
        )
    elif inventory_note:
        parts.append(inventory_note)
    parts.append("How many nights will your group stay?")
    return " ".join(p.strip() for p in parts if p.strip())


def compose_nights_complete_reply(
    *,
    arrival_label: str,
    nights: int,
    headcount: int | None,
    inventory_note: str | None,
) -> str:
    msg = f"Perfect — {arrival_label} for {nights} night{'s' if nights != 1 else ''}"
    if headcount:
        msg += f" with {headcount} participants on your cards"
    msg += "."
    if inventory_note:
        msg += f" {inventory_note}"
    msg += " Your summary cards on the right are updated."
    return msg


def compose_room_block_capacity_reply(
    *,
    headcount: int | None,
    peak_rooms: int,
    rooms_free: int | None,
    check_in_label: str | None,
    fits: bool = False,
) -> str:
    guests = headcount or peak_rooms
    lead = f"Got it — {peak_rooms} rooms for {guests} guests on your block."
    if rooms_free is None or not check_in_label:
        return (
            f"{lead} Share your arrival date or say next week and I'll check live inventory "
            "against that peak."
        )
    if fits and rooms_free >= peak_rooms:
        return (
            f"{lead} On {check_in_label} inventory shows about {rooms_free} rooms free, "
            "which covers that peak. How many nights should I hold?"
        )
    return (
        f"{lead} On {check_in_label} we only have about {rooms_free} rooms free — "
        f"we can't hold {peak_rooms} single-occupancy rooms that night. "
        "We could use doubles, reduce the block, or pick another date — what works best?"
    )
