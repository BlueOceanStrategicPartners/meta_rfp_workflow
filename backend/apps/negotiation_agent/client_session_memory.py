"""Client portal session memory — card edits, clarifications, voice context (designer-parity lite)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from apps.negotiation_agent.client_agent_context import format_cards_for_prompt
from apps.rfp_debate.models import RFPSubmission

MAX_EVENTS = 40
MAX_TRANSCRIPT_TURNS = 30
MEMORY_PREFIX = (
    "CLIENT SESSION MEMORY (authoritative — prefer over older chat; never mention floor prices aloud):"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cards_fingerprint(cards: dict | None) -> str:
    blob = json.dumps(cards or {}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()[:16]


def default_session() -> dict[str, Any]:
    return {
        "events": [],
        "transcript": [],
        "clarification_options": [],
        "agent_todos": [],
        "last_cards_hash": "",
        "intake": {},
    }


def normalize_session(raw: dict | None) -> dict[str, Any]:
    base = default_session()
    if not isinstance(raw, dict):
        return base
    events = raw.get("events")
    if isinstance(events, list):
        base["events"] = [e for e in events if isinstance(e, dict)][-MAX_EVENTS:]
    transcript = raw.get("transcript")
    if isinstance(transcript, list):
        cleaned_transcript: list[dict[str, Any]] = []
        for turn in transcript:
            if not isinstance(turn, dict):
                continue
            role = str(turn.get("role") or "")
            if role not in ("user", "assistant"):
                continue
            cleaned_transcript.append(
                {
                    "role": role,
                    "text": str(turn.get("text") or "")[:2000],
                    "at": str(turn.get("at") or "")[:32],
                }
            )
        base["transcript"] = cleaned_transcript[-MAX_TRANSCRIPT_TURNS:]
    opts = raw.get("clarification_options")
    if isinstance(opts, list):
        base["clarification_options"] = [str(o) for o in opts if o][:8]
    todos = raw.get("agent_todos")
    if isinstance(todos, list):
        cleaned: list[dict[str, Any]] = []
        for t in todos:
            if not isinstance(t, dict):
                continue
            cleaned.append(
                {
                    "id": str(t.get("id") or len(cleaned) + 1),
                    "text": str(t.get("text") or "")[:200],
                    "status": str(t.get("status") or "pending"),
                }
            )
        base["agent_todos"] = cleaned[:16]
    if raw.get("last_cards_hash"):
        base["last_cards_hash"] = str(raw["last_cards_hash"])[:16]
    intake = raw.get("intake")
    if isinstance(intake, dict):
        base["intake"] = {
            k: str(v)[:32]
            for k, v in intake.items()
            if k in (
                "check_in_iso",
                "pending_field",
                "availability_window_start",
                "availability_window_days",
                "headcount",
                "peak_rooms",
                "room_nights",
                "nights",
                "needs_meeting_space",
            )
        }
    handoff = raw.get("turn_handoff")
    if isinstance(handoff, dict):
        from apps.negotiation_agent.client_turn_handoff import normalize_turn_handoff

        normalized = normalize_turn_handoff(handoff)
        if normalized:
            base["turn_handoff"] = normalized
    archived = raw.get("archived")
    base["archived"] = archived is True or str(archived).lower() in {"1", "true", "yes"}
    return base


def append_session_event(
    rfp: RFPSubmission,
    *,
    event_type: str,
    summary: str,
    meta: dict | None = None,
) -> dict[str, Any]:
    session = normalize_session(getattr(rfp, "client_session_json", None))
    entry = {
        "at": _utc_now_iso(),
        "type": event_type[:32],
        "summary": summary.strip()[:400],
    }
    if meta:
        entry["meta"] = {k: str(v)[:120] for k, v in meta.items()}
    session["events"] = (session["events"] + [entry])[-MAX_EVENTS:]
    rfp.client_session_json = session
    return session


def sync_clarifications_from_cards(rfp: RFPSubmission) -> dict[str, Any]:
    """Derive clarification chips and todos from cards + amber fields (Phase 3)."""
    from apps.negotiation_agent.meeting_space_intent import meeting_space_wanted_for_cards

    session = normalize_session(rfp.client_session_json)
    cards = rfp.active_ui_cards_json or {}
    overview = cards.get("event_overview") or {}
    meeting = cards.get("meeting_space") or {}
    room = cards.get("room_block") or {}

    clarifications: list[str] = []
    todos: list[dict[str, Any]] = []

    amber_overview = set(overview.get("amber_fields") or [])
    if "check_in_date" in amber_overview or not (overview.get("check_in_date") or "").strip():
        clarifications.append("Confirm your check-in date on the cards")
        todos.append({"id": "dates", "text": "Confirm travel dates", "status": "pending"})
    if "check_out_date" in amber_overview or not (overview.get("check_out_date") or "").strip():
        if "Confirm your check-out date on the cards" not in clarifications:
            clarifications.append("Confirm your check-out date on the cards")

    amber_room = set(room.get("amber_fields") or [])
    if "total_room_nights" in amber_room or not room.get("total_room_nights"):
        clarifications.append("Confirm room nights for your block")
        todos.append({"id": "nights", "text": "Set room block nights", "status": "pending"})

    try:
        headcount = int(meeting.get("headcount") or 0)
    except (TypeError, ValueError):
        headcount = 0
    if headcount <= 0:
        intake = session.get("intake") or {}
        if isinstance(intake, dict):
            try:
                headcount = int(intake.get("headcount") or 0)
            except (TypeError, ValueError):
                headcount = 0
    if headcount <= 0:
        try:
            peak_only = int(room.get("peak_rooms") or 0)
        except (TypeError, ValueError):
            peak_only = 0
        if peak_only <= 0 and meeting_space_wanted_for_cards(cards, session):
            clarifications.append("Add meeting headcount on the cards")
            todos.append({"id": "headcount", "text": "Add meeting headcount", "status": "pending"})

    check_in = (overview.get("check_in_date") or "").strip()
    check_out = (overview.get("check_out_date") or "").strip()
    room_nights = room.get("total_room_nights")

    if headcount > 0:
        for t in todos:
            if t.get("id") == "headcount":
                t["status"] = "done"
    if check_in and check_out:
        for t in todos:
            if t.get("id") == "dates":
                t["status"] = "done"
    if room_nights:
        for t in todos:
            if t.get("id") == "nights":
                t["status"] = "done"

    session["clarification_options"] = clarifications[:8]
    session["agent_todos"] = todos[:16]
    session["last_cards_hash"] = cards_fingerprint(cards)
    rfp.client_session_json = session
    from apps.negotiation_agent.client_turn_handoff import refresh_turn_handoff

    refresh_turn_handoff(rfp)
    return normalize_session(rfp.client_session_json)


def summarize_cards_for_agent(rfp: RFPSubmission) -> str:
    return format_cards_for_prompt(rfp)


def build_agent_context_block(rfp: RFPSubmission | None) -> str:
    if not rfp:
        return ""
    session = normalize_session(rfp.client_session_json)
    from apps.negotiation_agent.client_turn_handoff import (
        build_turn_handoff,
        format_turn_handoff_for_prompt,
    )

    handoff = session.get("turn_handoff") or build_turn_handoff(rfp)
    parts = [
        MEMORY_PREFIX,
        format_turn_handoff_for_prompt(handoff),
        summarize_cards_for_agent(rfp),
    ]
    recent = session["events"][-8:]
    if recent:
        parts.append("Recent session events:")
        for ev in recent:
            parts.append(f"- [{ev.get('type')}] {ev.get('summary')}")
        proposal_ev = [e for e in recent if str(e.get("type") or "").startswith("proposal_")]
        if proposal_ev:
            parts.append(
                "Recent proposal UI actions (client full-screen proposal — treat as authoritative intent):"
            )
            for ev in proposal_ev[-5:]:
                parts.append(f"- {ev.get('summary')}")
    opts = session.get("clarification_options") or []
    if opts:
        parts.append("Open clarifications: " + "; ".join(opts[:6]))
    todos = [t for t in (session.get("agent_todos") or []) if t.get("status") == "pending"]
    if todos:
        parts.append(
            "Pending checklist: "
            + "; ".join(str(t.get("text")) for t in todos[:6])
        )
    transcript = session.get("transcript") or []
    recent_dialogue = transcript[-8:]
    if recent_dialogue:
        parts.append("Recent dialogue:")
        for turn in recent_dialogue:
            role = turn.get("role") or "user"
            label = "Client" if role == "user" else "Assistant"
            parts.append(f"{label}: {turn.get('text') or ''}")
    intake = session.get("intake") or {}
    if isinstance(intake, dict) and intake.get("check_in_iso"):
        parts.append(
            f"Intake state: preferred check-in {intake.get('check_in_iso')}; "
            f"still need: {intake.get('pending_field') or 'details'}."
        )
    from apps.negotiation_agent.client_group_context import resolve_stored_headcount

    hc = resolve_stored_headcount(rfp)
    if hc:
        parts.append(
            f"Group size on record: {hc} participants — confirm or update only if the client "
            "changes it; do not ask for headcount again."
        )
    return "\n".join(parts)


def describe_card_patch(patch: dict) -> str:
    bits: list[str] = []
    overview = patch.get("event_overview") or {}
    if overview.get("check_in_date") or overview.get("check_out_date"):
        bits.append(
            f"dates {overview.get('check_in_date') or '?'} → {overview.get('check_out_date') or '?'}"
        )
    meeting = patch.get("meeting_space") or {}
    if meeting.get("headcount") is not None:
        bits.append(f"headcount {meeting.get('headcount')}")
    if meeting.get("seating_style"):
        bits.append(f"seating {meeting.get('seating_style')}")
    room = patch.get("room_block") or {}
    if room.get("total_room_nights") is not None:
        bits.append(f"{room.get('total_room_nights')} room nights")
    if room.get("peak_rooms") is not None:
        bits.append(f"{room.get('peak_rooms')} peak rooms")
    catering_av = patch.get("catering_av") or {}
    if catering_av.get("catering"):
        bits.append("catering notes")
    if catering_av.get("av"):
        bits.append("AV specs")
    return ", ".join(bits) if bits else "event details"


def build_card_mutation_ack(patch: dict, cards: dict) -> str:
    detail = describe_card_patch(patch)
    quote = (cards.get("live_quote") or {}).get("anchor_price")
    msg = f"Got it — I updated {detail} on your summary cards."
    if quote:
        try:
            formatted = f"${int(float(quote)):,}"
        except (TypeError, ValueError):
            formatted = str(quote)
        msg += f" Your preliminary estimate is now {formatted}."
    return msg


def _append_transcript_turn(
    session: dict[str, Any],
    *,
    role: str,
    text: str,
) -> None:
    turn = {
        "role": role,
        "text": text.strip()[:2000],
        "at": _utc_now_iso(),
    }
    session["transcript"] = (session.get("transcript") or []) + [turn]
    session["transcript"] = session["transcript"][-MAX_TRANSCRIPT_TURNS:]


def record_assistant_reply(rfp: RFPSubmission, text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    session = normalize_session(getattr(rfp, "client_session_json", None))
    _append_transcript_turn(session, role="assistant", text=cleaned)
    entry = {
        "at": _utc_now_iso(),
        "type": "assistant_reply",
        "summary": cleaned[:400],
    }
    session["events"] = (session.get("events") or []) + [entry]
    session["events"] = session["events"][-MAX_EVENTS:]
    rfp.client_session_json = session
    from apps.negotiation_agent.client_turn_handoff import refresh_turn_handoff

    refresh_turn_handoff(rfp)


def _sanitize_user_message_text(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.lower().startswith("undefined"):
        cleaned = cleaned[len("undefined") :].strip()
    return cleaned


def record_voice_turn(rfp: RFPSubmission, user_message: str) -> None:
    cleaned = _sanitize_user_message_text(user_message)
    if cleaned:
        from .meeting_space_intent import (
            try_apply_meeting_space_decline,
            try_apply_meeting_space_request,
        )

        if try_apply_meeting_space_decline(rfp, cleaned) or try_apply_meeting_space_request(rfp, cleaned):
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])

    session = normalize_session(getattr(rfp, "client_session_json", None))
    if cleaned:
        transcript = session.get("transcript") or []
        if transcript:
            last = transcript[-1]
            if (
                last.get("role") == "user"
                and (last.get("text") or "").strip() == cleaned[:2000]
            ):
                rfp.client_session_json = session
                return
        _append_transcript_turn(session, role="user", text=cleaned)
        rfp.client_session_json = session
        from apps.negotiation_agent.client_turn_handoff import refresh_turn_handoff

        refresh_turn_handoff(rfp)
    append_session_event(
        rfp,
        event_type="voice",
        summary=f"Client said: {cleaned[:180]}",
    )
