"""Compact session summaries for the client portal history rail."""
from __future__ import annotations

from apps.negotiation_agent.client_session_memory import normalize_session
from apps.rfp_debate.models import RFPStatus, RFPSubmission

COMPLETED_STATUSES = frozenset({RFPStatus.PROPOSAL_RENDERED, RFPStatus.BOOKED})


def _session_title(rfp: RFPSubmission) -> str:
    overview = (rfp.active_ui_cards_json or {}).get("event_overview") or {}
    company = (overview.get("company_name") or "").strip()
    if company and company.upper() != "TBD":
        return company[:80]
    text = (rfp.source_document_text or "").strip()
    if text:
        return text.split("\n", 1)[0][:80]
    return f"RFP · {rfp.created_at.strftime('%b %d, %Y') if rfp.created_at else 'Session'}"


def _last_snippet(rfp: RFPSubmission) -> str:
    session = normalize_session(rfp.client_session_json)
    transcript = session.get("transcript") or []
    if transcript:
        turn = transcript[-1]
        role = "You" if turn.get("role") == "user" else "Agent"
        text = str(turn.get("text") or "").strip()
        if text:
            return f"{role}: {text[:140]}"
    events = session.get("events") or []
    if events:
        return str(events[-1].get("summary") or "")[:160]
    text = (rfp.source_document_text or "").strip()
    return text[:160] if text else "No messages yet."


def _proposal_card(rfp: RFPSubmission) -> dict:
    cards = rfp.active_ui_cards_json or {}
    overview = cards.get("event_overview") or {}
    room = cards.get("room_block") or {}
    quote = cards.get("live_quote") or {}
    meeting = cards.get("meeting_space") or {}
    return {
        "company_name": overview.get("company_name") or "",
        "check_in_date": overview.get("check_in_date") or "",
        "check_out_date": overview.get("check_out_date") or "",
        "peak_rooms": room.get("peak_rooms"),
        "headcount": meeting.get("headcount"),
        "estimate": quote.get("anchor_price") or quote.get("target_price"),
    }


def serialize_rfp_session_summary(rfp: RFPSubmission) -> dict:
    completed = rfp.status in COMPLETED_STATUSES
    return {
        "id": str(rfp.id),
        "status": rfp.status,
        "completed": completed,
        "title": _session_title(rfp),
        "updated_at": rfp.updated_at.isoformat() if rfp.updated_at else "",
        "created_at": rfp.created_at.isoformat() if rfp.created_at else "",
        "last_snippet": _last_snippet(rfp),
        "proposal_card": _proposal_card(rfp) if completed else None,
    }
