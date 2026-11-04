"""Intake gate pipeline — slot extraction, state machine, business rules, reply composition."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from apps.rfp_debate.models import RFPSubmission

from .client_group_context import (
    message_sets_new_headcount,
    persist_group_size_to_intake,
    resolve_peak_rooms,
    resolve_stored_headcount,
)
from .client_session_memory import build_agent_context_block, normalize_session
from .voice_card_updates import VoiceDateValidationError, parse_voice_card_patch
from .voice_dates import (
    message_mentions_checkin,
    message_mentions_checkout,
    parse_arrival_date_from_voice,
    parse_duration_nights_from_voice,
    parse_weekday_index,
    validate_stay_not_in_past,
    voice_today,
    resolve_weekday_in_window,
)
from .voice_intake_apply import apply_stay_patch, build_stay_patch_from_dates
from .voice_prompts import compose_arrival_nights_reply, compose_nights_complete_reply
from apps.inventory.room_availability import inventory_capacity_warning, inventory_fits_block


class IntakeGate(str, Enum):
    """Ordered gates — first matching handler wins."""
    NIGHTS_COMPLETION = "nights_completion"
    ARRIVAL_PENDING_NIGHTS = "arrival_pending_nights"
    NO_MATCH = "no_match"


@dataclass
class IntakeSlots:
    check_in: date | None = None
    check_out: date | None = None
    nights: int | None = None
    headcount: int | None = None
    peak_rooms: int | None = None
    patch: dict[str, Any] | None = None


@dataclass
class IntakeGateResult:
    gate: IntakeGate
    spoken: str
    slots: IntakeSlots = field(default_factory=IntakeSlots)


def _intake_block(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get("intake")
    return raw if isinstance(raw, dict) else {}


def availability_window(session: dict[str, Any]) -> tuple[date | None, int]:
    intake = _intake_block(session)
    start_raw = (intake.get("availability_window_start") or "").strip()
    days = int(intake.get("availability_window_days") or 7)
    if not start_raw:
        return None, days
    try:
        return date.fromisoformat(start_raw[:10]), days
    except ValueError:
        return None, days


def _message_mentions_arrival(message: str) -> bool:
    lower = message.lower()
    if parse_arrival_date_from_voice(message) is not None:
        return True
    return any(
        w in lower
        for w in (
            "arriv",
            "come",
            "visit",
            "check in",
            "check-in",
            "allowed",
            "allow",
            "allow us",
            "host us",
            "hold that date",
        )
    )


def _spoken_arrival_label(check_in: date) -> str:
    return check_in.strftime("%A, %B %d")


def _apply_patch(rfp: RFPSubmission, patch: dict[str, Any]) -> None:
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(str(rfp.id), patch)
    rfp.refresh_from_db()


def _save_intake_pending(
    rfp: RFPSubmission,
    *,
    check_in_iso: str,
    pending_field: str,
) -> None:
    session = normalize_session(rfp.client_session_json)
    intake = _intake_block(session)
    intake["check_in_iso"] = check_in_iso
    intake["pending_field"] = pending_field
    session["intake"] = intake
    rfp.client_session_json = session


def _arrival_permission_ask(message: str) -> bool:
    """Host/allow arrival — not 'can we take 100 rooms'."""
    lower = (message or "").lower()
    if re.search(r"\bcan we take\b|\bcan we get\b|\btake up\b|\b(\d+|hundred)\s*rooms?\b", lower):
        if re.search(r"\bcan we\b|\bcould we\b", lower):
            return False
    return any(
        w in lower
        for w in (
            "allow us",
            "allowed us",
            "allow to come",
            "could we come",
            "can we come",
            "host us",
            "hold that date",
        )
    )


def _adjust_arrival_for_group_block(
    slots: IntakeSlots,
    message: str,
    rfp: RFPSubmission,
) -> None:
    """Same weekday as today + large block → next-week window, not same-day arrival."""
    ref = voice_today()
    if slots.check_in is None:
        return
    weekday = parse_weekday_index(message)
    if weekday is None:
        return
    needed = slots.peak_rooms or slots.headcount or resolve_stored_headcount(rfp) or 0
    if needed < 10:
        return
    if slots.check_in != ref or weekday != ref.weekday():
        return
    session = normalize_session(rfp.client_session_json)
    window_start, window_days = availability_window(session)
    if window_start is None:
        from apps.inventory.room_availability import next_calendar_week_range

        window_start, end = next_calendar_week_range(ref=ref)
        window_days = (end - window_start).days + 1
    alt = resolve_weekday_in_window(weekday, window_start, window_days)
    if alt and alt > ref:
        slots.check_in = alt
        if slots.patch is not None:
            slots.patch.setdefault("event_overview", {})["check_in_date"] = alt.isoformat()


def extract_intake_slots(rfp: RFPSubmission, message: str) -> IntakeSlots:
    session = normalize_session(rfp.client_session_json)
    cleaned = (message or "").strip()
    if cleaned and "next week" in cleaned.lower():
        window_start, _ = availability_window(session)
        if window_start is None:
            from apps.inventory.room_availability import build_availability_table

            from .voice_intake import record_availability_window

            table = build_availability_table()
            if table.get("rows"):
                record_availability_window(rfp, table)
                session = normalize_session(rfp.client_session_json)
    window_start, window_days = availability_window(session)
    patch = parse_voice_card_patch(
        message,
        availability_window_start=window_start,
        availability_window_days=window_days,
    )

    slots = IntakeSlots(patch=patch)
    if patch:
        ov = patch.get("event_overview") or {}
        if ov.get("check_in_date"):
            try:
                slots.check_in = date.fromisoformat(str(ov["check_in_date"])[:10])
            except ValueError:
                pass
        if ov.get("check_out_date"):
            try:
                slots.check_out = date.fromisoformat(str(ov["check_out_date"])[:10])
            except ValueError:
                pass
        rb = patch.get("room_block") or {}
        if rb.get("total_room_nights"):
            slots.nights = int(rb["total_room_nights"])
        if rb.get("peak_rooms"):
            slots.peak_rooms = int(rb["peak_rooms"])
        ms = patch.get("meeting_space") or {}
        if ms.get("headcount"):
            slots.headcount = int(ms["headcount"])

    if slots.nights is None:
        dur = parse_duration_nights_from_voice(cleaned)
        if dur:
            slots.nights = dur

    checkout_only = message_mentions_checkout(cleaned) and not message_mentions_checkin(cleaned)
    if slots.check_in is None and not checkout_only and (
        parse_weekday_index(message) is not None or _message_mentions_arrival(message)
    ):
        resolved = parse_arrival_date_from_voice(
            message,
            availability_window_start=window_start,
            availability_window_days=window_days,
            ref=voice_today(),
        )
        if resolved:
            slots.check_in = resolved

    stored_hc = resolve_stored_headcount(rfp)
    if slots.headcount is None and stored_hc:
        slots.headcount = stored_hc
    if slots.peak_rooms is None and slots.headcount:
        slots.peak_rooms = resolve_peak_rooms(rfp, headcount=slots.headcount) or slots.headcount
    if re.search(r"\b(\d+|hundred)\s*rooms?\b", (message or "").lower()):
        peak_from_msg = (slots.patch or {}).get("room_block", {}).get("peak_rooms")
        if peak_from_msg:
            slots.peak_rooms = int(peak_from_msg)
    _adjust_arrival_for_group_block(slots, message, rfp)
    return slots


def _complete_stay_if_ready(
    rfp: RFPSubmission,
    slots: IntakeSlots,
    session: dict[str, Any],
    intake: dict[str, Any],
) -> IntakeGateResult | None:
    """Apply full stay when patch or slots already have check-in and check-out."""
    patch = slots.patch or {}
    ov = patch.get("event_overview") or {}
    rb = patch.get("room_block") or {}

    check_in = slots.check_in
    check_out = slots.check_out
    if check_in is None and ov.get("check_in_date"):
        try:
            check_in = date.fromisoformat(str(ov["check_in_date"])[:10])
        except ValueError:
            check_in = None
    if check_out is None and ov.get("check_out_date"):
        try:
            check_out = date.fromisoformat(str(ov["check_out_date"])[:10])
        except ValueError:
            check_out = None
    if check_in is None or check_out is None:
        return None

    nights = slots.nights or rb.get("total_room_nights")
    if not nights:
        nights = max(1, (check_out - check_in).days)
    n = int(nights)
    peak = slots.peak_rooms or resolve_peak_rooms(rfp, headcount=slots.headcount)
    hc = slots.headcount or resolve_stored_headcount(rfp)
    stay_patch = build_stay_patch_from_dates(
        check_in=check_in,
        check_out=check_out,
        headcount=hc,
        peak_rooms=peak,
    )
    apply_stay_patch(rfp, stay_patch)
    cap = inventory_capacity_warning(check_in, peak or hc or 0) if (peak or hc) else None
    spoken = compose_nights_complete_reply(
        arrival_label=_spoken_arrival_label(check_in),
        nights=n,
        headcount=hc,
        inventory_note=cap,
    )
    return IntakeGateResult(gate=IntakeGate.NIGHTS_COMPLETION, spoken=spoken, slots=slots)


def run_intake_gate_pipeline(rfp: RFPSubmission, message: str) -> IntakeGateResult | str | None:
    """
    Gate-check intake orchestrator.
    Returns spoken str (validation error), IntakeGateResult, or None to fall through.
    """
    cleaned = (message or "").strip()
    if not cleaned:
        return None

    try:
        slots = extract_intake_slots(rfp, cleaned)
    except VoiceDateValidationError as exc:
        return exc.message

    session = normalize_session(rfp.client_session_json)
    intake = _intake_block(session)

    completed = _complete_stay_if_ready(rfp, slots, session, intake)
    if completed:
        return completed

    pending_check_in = (intake.get("check_in_iso") or "").strip()
    if pending_check_in and slots.nights and intake.get("pending_field") == "nights":
        try:
            check_in = date.fromisoformat(pending_check_in[:10])
        except ValueError:
            check_in = None
        if check_in:
            n = int(slots.nights)
            check_out = check_in + timedelta(days=max(1, n))
            peak = slots.peak_rooms or resolve_peak_rooms(rfp, headcount=slots.headcount)
            hc = slots.headcount or resolve_stored_headcount(rfp)
            full_patch: dict[str, Any] = {
                "event_overview": {
                    "check_in_date": check_in.isoformat(),
                    "check_out_date": check_out.isoformat(),
                },
                "room_block": {"total_room_nights": n},
            }
            if hc:
                full_patch["meeting_space"] = {"headcount": hc}
                if peak:
                    full_patch["room_block"]["peak_rooms"] = peak
            _apply_patch(rfp, full_patch)
            intake["pending_field"] = ""
            session["intake"] = intake
            rfp.client_session_json = session
            cap = inventory_capacity_warning(check_in, peak or hc or 0) if (peak or hc) else None
            spoken = compose_nights_complete_reply(
                arrival_label=_spoken_arrival_label(check_in),
                nights=n,
                headcount=hc,
                inventory_note=cap,
            )
            return IntakeGateResult(gate=IntakeGate.NIGHTS_COMPLETION, spoken=spoken, slots=slots)

    if slots.check_in is None:
        return None
    if slots.nights:
        if slots.check_out:
            completed = _complete_stay_if_ready(rfp, slots, session, intake)
            if completed:
                return completed
        arrival = slots.check_in
        # Duration already known (e.g. "only one day") — complete stay without re-asking nights.
        n = int(slots.nights)
        check_out = arrival + timedelta(days=max(1, n))
        peak = slots.peak_rooms or resolve_peak_rooms(rfp, headcount=slots.headcount)
        hc = slots.headcount or resolve_stored_headcount(rfp)
        full_patch: dict[str, Any] = {
            "event_overview": {
                "check_in_date": arrival.isoformat(),
                "check_out_date": check_out.isoformat(),
            },
            "room_block": {"total_room_nights": n},
        }
        if hc:
            full_patch["meeting_space"] = {"headcount": hc}
            if peak:
                full_patch["room_block"]["peak_rooms"] = peak
        _apply_patch(rfp, full_patch)
        intake["pending_field"] = ""
        intake["check_in_iso"] = arrival.isoformat()
        session["intake"] = intake
        rfp.client_session_json = session
        cap = inventory_capacity_warning(arrival, peak or hc or 0) if (peak or hc) else None
        spoken = compose_nights_complete_reply(
            arrival_label=_spoken_arrival_label(arrival),
            nights=n,
            headcount=hc,
            inventory_note=cap,
        )
        return IntakeGateResult(gate=IntakeGate.NIGHTS_COMPLETION, spoken=spoken, slots=slots)

    err = validate_stay_not_in_past(slots.check_in, slots.check_in)
    if err:
        return err

    arrival = slots.check_in
    hc = slots.headcount
    peak = slots.peak_rooms or (hc if hc else None)
    if hc:
        persist_group_size_to_intake(rfp, headcount=hc, peak_rooms=peak or hc)

    _save_intake_pending(rfp, check_in_iso=arrival.isoformat(), pending_field="nights")
    partial: dict[str, Any] = {"event_overview": {"check_in_date": arrival.isoformat()}}
    if hc:
        partial["meeting_space"] = {"headcount": hc}
        if peak:
            partial.setdefault("room_block", {})["peak_rooms"] = peak
    try:
        _apply_patch(rfp, partial)
    except Exception:
        pass

    cap = inventory_capacity_warning(arrival, peak or hc or 0) if (peak or hc) else None
    free, _fits = inventory_fits_block(arrival, peak or hc or 0)
    permission = _arrival_permission_ask(cleaned) and not (
        free is not None and (peak or hc or 0) > free
    )
    spoken = compose_arrival_nights_reply(
        arrival_label=_spoken_arrival_label(arrival),
        headcount=hc,
        peak_rooms=peak,
        inventory_note=cap,
        permission_ask=permission,
        confirm_stored_group=bool(hc and not message_sets_new_headcount(cleaned)),
        rooms_free=free,
        rooms_needed=peak or hc,
    )
    return IntakeGateResult(gate=IntakeGate.ARRIVAL_PENDING_NIGHTS, spoken=spoken, slots=slots)


def build_llm_intake_context(rfp: RFPSubmission) -> str:
    """Session block for optional LLM slot/reply tier (gate fallback)."""
    return build_agent_context_block(rfp)
