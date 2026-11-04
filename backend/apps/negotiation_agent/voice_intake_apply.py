"""Persist intake slots (deterministic or LLM) onto UI cards."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.rfp_debate.models import RFPSubmission

from .client_group_context import resolve_peak_rooms, resolve_stored_headcount
from .client_session_memory import normalize_session
from .voice_dates import validate_stay_not_in_past


def _apply_patch(rfp: RFPSubmission, patch: dict[str, Any]) -> None:
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(str(rfp.id), patch)
    rfp.refresh_from_db()


def merge_stay_patch_with_voice_extras(
    stay_patch: dict[str, Any],
    voice_patch: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep intake stay fields while merging seating/catering from the same utterance."""
    if not voice_patch:
        return stay_patch
    merged = dict(stay_patch)
    for key in ("meeting_space", "catering_av"):
        chunk = voice_patch.get(key)
        if isinstance(chunk, dict) and chunk:
            merged[key] = {**(merged.get(key) or {}), **chunk}
    return merged


def build_stay_patch_from_dates(
    *,
    check_in: date,
    check_out: date,
    headcount: int | None = None,
    peak_rooms: int | None = None,
) -> dict[str, Any]:
    nights = max(1, (check_out - check_in).days)
    patch: dict[str, Any] = {
        "event_overview": {
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        },
        "room_block": {"total_room_nights": nights},
    }
    if headcount and headcount > 0:
        patch["meeting_space"] = {"headcount": headcount}
    peak = peak_rooms or (headcount if headcount else None)
    if peak and peak > 0:
        patch["room_block"]["peak_rooms"] = peak
    return patch


def apply_stay_patch(rfp: RFPSubmission, patch: dict[str, Any]) -> None:
    _apply_patch(rfp, patch)
    session = normalize_session(rfp.client_session_json)
    intake = session.get("intake") if isinstance(session.get("intake"), dict) else {}
    ov = patch.get("event_overview") or {}
    if ov.get("check_in_date"):
        intake["check_in_iso"] = str(ov["check_in_date"])[:10]
    intake["pending_field"] = ""
    rb = patch.get("room_block") or {}
    if rb.get("total_room_nights"):
        intake["room_nights"] = str(rb["total_room_nights"])
    session["intake"] = intake
    rfp.client_session_json = session


def apply_intake_classification_to_cards(rfp: RFPSubmission, raw: dict[str, Any]) -> bool:
    """Merge high-confidence LLM intake JSON onto cards. Returns True if cards updated."""
    if not isinstance(raw, dict):
        return False
    intent = str(raw.get("intent") or "")
    check_in_raw = (raw.get("check_in_iso") or "").strip()
    nights_raw = raw.get("nights")
    try:
        nights = int(nights_raw) if nights_raw is not None else 0
    except (TypeError, ValueError):
        nights = 0

    if intent not in ("set_stay_complete", "set_arrival", "set_nights") and not check_in_raw:
        return False

    patch: dict[str, Any] = {}
    if check_in_raw and nights > 0:
        try:
            check_in = date.fromisoformat(check_in_raw[:10])
        except ValueError:
            return False
        check_out = check_in + timedelta(days=max(1, nights))
        err = validate_stay_not_in_past(check_in, check_out)
        if err:
            return False
        hc = resolve_stored_headcount(rfp)
        try:
            hc_llm = int(raw.get("headcount") or 0)
            if hc_llm > 0:
                hc = hc_llm
        except (TypeError, ValueError):
            pass
        peak = resolve_peak_rooms(rfp, headcount=hc)
        try:
            peak_llm = int(raw.get("peak_rooms") or 0)
            if peak_llm > 0:
                peak = peak_llm
        except (TypeError, ValueError):
            pass
        patch = build_stay_patch_from_dates(
            check_in=check_in,
            check_out=check_out,
            headcount=hc,
            peak_rooms=peak,
        )
    elif check_in_raw and intent == "set_arrival":
        try:
            check_in = date.fromisoformat(check_in_raw[:10])
        except ValueError:
            return False
        err = validate_stay_not_in_past(check_in, check_in)
        if err:
            return False
        patch = {"event_overview": {"check_in_date": check_in.isoformat()}}
    else:
        return False

    if not patch:
        return False
    apply_stay_patch(rfp, patch)
    return True
