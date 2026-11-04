"""Compact JSON handoff for the next client voice turn — gathered / missing / ask_next."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from apps.rfp_debate.models import RFPSubmission

from .client_agent_context import read_cards_snapshot
from .client_group_context import participant_count_from_message, resolve_peak_rooms, resolve_stored_headcount
from .client_session_memory import normalize_session
from .voice_dates import parse_arrival_date_from_voice, voice_today

_GATHERED_KEYS = (
    "headcount",
    "room_nights",
    "peak_rooms",
    "check_in",
    "check_out",
    "seating_style",
    "organization",
)

_SLOT_LABELS: dict[str, str] = {
    "check_in_date": "check-in date",
    "check_out_date": "check-out date",
    "headcount": "meeting headcount",
    "room_nights": "length of stay (nights)",
    "peak_rooms": "peak room count",
}

_ASK_PROMPTS: dict[str, str] = {
    "check_in_date": "What check-in date works best for your group?",
    "check_out_date": "When will your group check out?",
    "headcount": "How many guests should I plan for in meeting space?",
    "room_nights": "How many nights should we hold on the room block?",
    "peak_rooms": "How many peak rooms do you need on the busiest night?",
}

_WORD_TO_INT: dict[str, int] = {
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
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _word_to_int(token: str) -> int | None:
    token = (token or "").strip().lower()
    if token.isdigit():
        return int(token)
    return _WORD_TO_INT.get(token)


def _room_nights_from_text(text: str) -> int | None:
    lower = (text or "").lower()
    if not re.search(r"\bnights?\b", lower):
        return None
    m = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b",
        lower,
    )
    if not m:
        return None
    return _word_to_int(m.group(1))


def _scan_transcript_user_texts(session: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for turn in session.get("transcript") or []:
        if not isinstance(turn, dict) or turn.get("role") != "user":
            continue
        t = str(turn.get("text") or "").strip()
        if t:
            texts.append(t)
    return texts


def _resolve_check_in_from_session(rfp: RFPSubmission, session: dict[str, Any]) -> str | None:
    cards = read_cards_snapshot(rfp)
    overview = cards["event_overview"]
    cin = (overview.get("check_in_date") or "").strip()
    if cin and cin.upper() != "TBD":
        return cin[:32]
    intake = session.get("intake") if isinstance(session.get("intake"), dict) else {}
    iso = (intake.get("check_in_iso") or "").strip()
    if iso:
        return iso[:32]
    ref = voice_today()
    for text in reversed(_scan_transcript_user_texts(session)):
        parsed = parse_arrival_date_from_voice(text, ref=ref)
        if parsed is not None:
            return parsed.isoformat()
    return None


def _resolve_check_out_from_session(rfp: RFPSubmission, session: dict[str, Any]) -> str | None:
    cards = read_cards_snapshot(rfp)
    overview = cards["event_overview"]
    cout = (overview.get("check_out_date") or "").strip()
    if cout and cout.upper() != "TBD":
        return cout[:32]
    return None


def _resolve_room_nights(rfp: RFPSubmission, session: dict[str, Any]) -> int | None:
    cards = read_cards_snapshot(rfp)
    room = cards["room_block"]
    try:
        n = int(room.get("total_room_nights") or 0)
        if n > 0:
            return n
    except (TypeError, ValueError):
        pass
    intake = session.get("intake") if isinstance(session.get("intake"), dict) else {}
    for key in ("room_nights", "nights"):
        try:
            n = int(intake.get(key) or 0)
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass
    for text in reversed(_scan_transcript_user_texts(session)):
        n = _room_nights_from_text(text)
        if n and n > 0:
            return n
    return None


def derive_gathered_facts(rfp: RFPSubmission) -> dict[str, Any]:
    session = normalize_session(rfp.client_session_json)
    cards = read_cards_snapshot(rfp)
    overview = cards["event_overview"]
    meeting = cards["meeting_space"]
    room = cards["room_block"]

    gathered: dict[str, Any] = {}
    org = (overview.get("company_name") or "").strip()
    if org and org.lower() not in {"voice rfp session", "your organization", "your organisation"}:
        gathered["organization"] = org[:80]

    hc = resolve_stored_headcount(rfp)
    if hc and hc > 0:
        gathered["headcount"] = hc

    peak = resolve_peak_rooms(rfp, headcount=hc)
    if peak and peak > 0:
        gathered["peak_rooms"] = peak

    nights = _resolve_room_nights(rfp, session)
    if nights:
        gathered["room_nights"] = nights

    cin = _resolve_check_in_from_session(rfp, session)
    if cin:
        gathered["check_in"] = cin
    cout = _resolve_check_out_from_session(rfp, session)
    if cout:
        gathered["check_out"] = cout

    seating = (meeting.get("seating_style") or "").strip()
    if seating:
        gathered["seating_style"] = seating[:32]

    return gathered


def derive_still_needed(rfp: RFPSubmission, gathered: dict[str, Any] | None = None) -> list[str]:
    g = gathered if gathered is not None else derive_gathered_facts(rfp)
    missing: list[str] = []
    if not g.get("check_in"):
        missing.append("check_in_date")
    if not g.get("check_out") and g.get("check_in") and not g.get("room_nights"):
        missing.append("check_out_date")
    if not g.get("room_nights") and g.get("check_in") and not g.get("check_out"):
        missing.append("room_nights")
    if not g.get("headcount"):
        missing.append("headcount")
    cards = read_cards_snapshot(rfp)
    room = cards["room_block"]
    try:
        peak_on_card = int(room.get("peak_rooms") or 0)
    except (TypeError, ValueError):
        peak_on_card = 0
    if g.get("headcount") and peak_on_card <= 0 and not g.get("peak_rooms"):
        missing.append("peak_rooms")
    return missing


def derive_ask_next(still_needed: list[str]) -> list[str]:
    prompts: list[str] = []
    for slot in still_needed[:4]:
        line = _ASK_PROMPTS.get(slot)
        if line and line not in prompts:
            prompts.append(line)
    return prompts[:3]


def build_turn_handoff(rfp: RFPSubmission) -> dict[str, Any]:
    gathered = derive_gathered_facts(rfp)
    still_needed = derive_still_needed(rfp, gathered)
    ask_next = derive_ask_next(still_needed)
    session = normalize_session(rfp.client_session_json)
    prior = session.get("turn_handoff")
    notes = ""
    if isinstance(prior, dict) and isinstance(prior.get("notes_for_next_turn"), str):
        notes = prior["notes_for_next_turn"][:240]
    return {
        "gathered": gathered,
        "still_needed": still_needed,
        "ask_next": ask_next,
        "notes_for_next_turn": notes,
        "updated_at": _utc_now_iso(),
    }


def normalize_turn_handoff(raw: dict | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    gathered_raw = raw.get("gathered")
    gathered: dict[str, Any] = {}
    if isinstance(gathered_raw, dict):
        for key in _GATHERED_KEYS:
            val = gathered_raw.get(key)
            if val is None or val == "":
                continue
            if key in ("headcount", "room_nights", "peak_rooms"):
                try:
                    gathered[key] = int(val)
                except (TypeError, ValueError):
                    continue
            else:
                gathered[key] = str(val)[:80]
    still_needed = raw.get("still_needed")
    cleaned_needed: list[str] = []
    if isinstance(still_needed, list):
        for item in still_needed:
            slot = str(item)[:32]
            if slot in _SLOT_LABELS or slot in _ASK_PROMPTS:
                cleaned_needed.append(slot)
    ask_next = raw.get("ask_next")
    cleaned_ask: list[str] = []
    if isinstance(ask_next, list):
        for item in ask_next:
            text = str(item).strip()[:200]
            if text:
                cleaned_ask.append(text)
    notes = str(raw.get("notes_for_next_turn") or "")[:240]
    updated = str(raw.get("updated_at") or "")[:32]
    return {
        "gathered": gathered,
        "still_needed": cleaned_needed[:8],
        "ask_next": cleaned_ask[:3],
        "notes_for_next_turn": notes,
        "updated_at": updated or _utc_now_iso(),
    }


def merge_llm_turn_handoff(
    base: dict[str, Any],
    llm_patch: dict | None,
) -> dict[str, Any]:
    """LLM may refine ask_next / notes; gathered facts stay card+transcript authoritative."""
    merged = dict(base)
    if not isinstance(llm_patch, dict):
        return merged
    llm_norm = normalize_turn_handoff(llm_patch)
    gathered = dict(merged.get("gathered") or {})
    for key, val in (llm_norm.get("gathered") or {}).items():
        if key not in gathered and val is not None:
            gathered[key] = val
    merged["gathered"] = gathered
    merged["still_needed"] = derive_still_needed_from_gathered(gathered)
    if llm_norm.get("ask_next"):
        merged["ask_next"] = llm_norm["ask_next"]
    else:
        merged["ask_next"] = derive_ask_next(merged["still_needed"])
    if llm_norm.get("notes_for_next_turn"):
        merged["notes_for_next_turn"] = llm_norm["notes_for_next_turn"]
    merged["updated_at"] = _utc_now_iso()
    return merged


def derive_still_needed_from_gathered(gathered: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not gathered.get("check_in"):
        missing.append("check_in_date")
    if not gathered.get("check_out") and gathered.get("check_in") and not gathered.get("room_nights"):
        missing.append("check_out_date")
    if not gathered.get("room_nights") and gathered.get("check_in") and not gathered.get("check_out"):
        missing.append("room_nights")
    if not gathered.get("headcount"):
        missing.append("headcount")
    if gathered.get("headcount") and not gathered.get("peak_rooms"):
        missing.append("peak_rooms")
    return missing


def refresh_turn_handoff(rfp: RFPSubmission) -> dict[str, Any]:
    handoff = build_turn_handoff(rfp)
    session = normalize_session(rfp.client_session_json)
    session["turn_handoff"] = handoff
    rfp.client_session_json = session
    return handoff


def apply_llm_turn_handoff(rfp: RFPSubmission, llm_patch: dict | None) -> dict[str, Any]:
    base = build_turn_handoff(rfp)
    handoff = merge_llm_turn_handoff(base, llm_patch)
    session = normalize_session(rfp.client_session_json)
    session["turn_handoff"] = handoff
    rfp.client_session_json = session
    return handoff


def format_turn_handoff_for_prompt(handoff: dict[str, Any]) -> str:
    if not handoff:
        return ""
    compact = {
        "gathered": handoff.get("gathered") or {},
        "still_needed": handoff.get("still_needed") or [],
        "ask_next": handoff.get("ask_next") or [],
    }
    notes = (handoff.get("notes_for_next_turn") or "").strip()
    blob = json.dumps(compact, separators=(",", ":"), default=str)
    lines = [
        "NEXT TURN HANDOFF (JSON — authoritative for follow-ups; do not re-ask gathered fields):",
        blob,
    ]
    if notes:
        lines.append(f"Note for next turn: {notes}")
    lines.append(
        "Ask at most ONE question from ask_next. If the client says they already told you, "
        "apologize briefly and only clarify still_needed using dialogue and gathered facts."
    )
    return "\n".join(lines)


def spoken_recap_from_handoff(rfp: RFPSubmission) -> str:
    handoff = build_turn_handoff(rfp)
    g = handoff.get("gathered") or {}
    bits: list[str] = []
    if g.get("headcount"):
        bits.append(f"{g['headcount']} guests")
    if g.get("room_nights"):
        n = int(g["room_nights"])
        bits.append(f"{n} night{'s' if n != 1 else ''}")
    if g.get("check_in"):
        bits.append(f"check-in {g['check_in']}")
    if g.get("check_out"):
        bits.append(f"check-out {g['check_out']}")
    if bits:
        lead = "You're right — I have " + ", ".join(bits) + " on record."
    else:
        lead = "You're right — let me use what you've already shared."
    ask = handoff.get("ask_next") or []
    if ask:
        return f"{lead} {ask[0]}"
    return f"{lead} Tell me if anything should change."


def client_message_signals_repeat_frustration(message: str) -> bool:
    lower = (message or "").lower()
    return bool(
        re.search(
            r"\b(already told|told you|said that|mentioned that|checking this)\b",
            lower,
        )
    )
