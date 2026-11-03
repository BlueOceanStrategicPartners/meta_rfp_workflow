"""Live negotiation monitor: list, human takeover, hand back, operator messages, conversation."""
from __future__ import annotations

from datetime import datetime

from apps.admin_command_center import audit
from apps.admin_command_center.models import AdminAuditEvent
from apps.rfp_debate.models import RFPStatus, RFPSubmission
from apps.rfp_debate.tasks import broadcast_rfp

from . import AdminConflictError, AdminInputError
from .rfps import company_name, quote_to_dict

ACTIVE_STATUSES = (
    RFPStatus.PRICING,
    RFPStatus.NEGOTIATING,
    RFPStatus.ESCALATED,
    RFPStatus.PROPOSAL_RENDERED,
)
TAKEOVER_ALLOWED = (
    RFPStatus.AWAITING_USER_CARD_EDIT,
    RFPStatus.PRICING,
    RFPStatus.NEGOTIATING,
    RFPStatus.PROPOSAL_RENDERED,
)
TAKEOVER_LINE = "A member of our events team is joining the conversation now."
RELEASE_LINE = "Thanks for waiting. I'll pick things up from here."
MAX_MESSAGE_CHARS = 500


def _last_takeover(rfp: RFPSubmission) -> AdminAuditEvent | None:
    return (
        AdminAuditEvent.objects.select_related("actor")
        .filter(target_type="rfp", target_id=str(rfp.id), action="negotiation.takeover")
        .first()
    )


def negotiation_list() -> list[dict]:
    rows = []
    for rfp in RFPSubmission.objects.filter(status__in=ACTIVE_STATUSES).order_by("-updated_at")[:100]:
        cards = rfp.active_ui_cards_json or {}
        overview = cards.get("event_overview") or {}
        meeting = cards.get("meeting_space") or {}
        latest = rfp.pricing_quotes.order_by("-created_at").first()
        taken_over = rfp.status == RFPStatus.ESCALATED
        takeover_event = _last_takeover(rfp) if taken_over else None
        rows.append(
            {
                "id": str(rfp.id),
                "company_name": company_name(rfp),
                "status": rfp.status,
                "taken_over": taken_over,
                "taken_over_by": (
                    takeover_event.actor.email if takeover_event and takeover_event.actor_id else None
                ),
                "check_in_date": overview.get("check_in_date"),
                "check_out_date": overview.get("check_out_date"),
                "headcount": meeting.get("headcount"),
                "latest_quote": quote_to_dict(latest) if latest else None,
                "updated_at": rfp.updated_at.isoformat(),
            }
        )
    return rows


def takeover(rfp: RFPSubmission, actor) -> RFPSubmission:
    if rfp.status == RFPStatus.ESCALATED:
        raise AdminConflictError("A person has already taken over this conversation.")
    if rfp.status not in TAKEOVER_ALLOWED:
        label = rfp.get_status_display().lower()
        raise AdminConflictError(f"This request is {label}; there is no live conversation to take over.")
    previous = rfp.status
    rfp.status = RFPStatus.ESCALATED
    rfp.save(update_fields=["status", "updated_at"])
    audit.record(actor, "negotiation.takeover", "rfp", rfp.id, previous_status=previous)
    broadcast_rfp(str(rfp.id), "agent_utterance", {"text": TAKEOVER_LINE})
    return rfp


def release(rfp: RFPSubmission, actor) -> RFPSubmission:
    if rfp.status != RFPStatus.ESCALATED:
        raise AdminConflictError("Nobody has taken over this conversation, so there is nothing to hand back.")
    event = _last_takeover(rfp)
    previous = (event.payload_json or {}).get("previous_status") if event else None
    if previous not in TAKEOVER_ALLOWED:
        previous = RFPStatus.NEGOTIATING
    rfp.status = previous
    rfp.save(update_fields=["status", "updated_at"])
    audit.record(actor, "negotiation.release", "rfp", rfp.id, restored_status=previous)
    broadcast_rfp(str(rfp.id), "agent_utterance", {"text": RELEASE_LINE})
    return rfp


def send_message(rfp: RFPSubmission, actor, text: str) -> None:
    clean = (text or "").strip()
    if not clean:
        raise AdminInputError("Write a message before sending.")
    if len(clean) > MAX_MESSAGE_CHARS:
        raise AdminInputError(f"Keep messages under {MAX_MESSAGE_CHARS} characters so they can be spoken.")
    if rfp.status != RFPStatus.ESCALATED:
        raise AdminConflictError("Take over the conversation before sending messages.")
    broadcast_rfp(str(rfp.id), "agent_utterance", {"text": clean})
    # Saved as an assistant turn so the AI knows what the person promised after hand back.
    from apps.negotiation_agent.client_session_memory import record_assistant_reply

    record_assistant_reply(rfp, clean)
    rfp.save(update_fields=["client_session_json", "updated_at"])
    audit.record(actor, "negotiation.message", "rfp", rfp.id, text=clean)


def _when(value: str) -> datetime:
    """All stored times are UTC; compare to the second (the chat history has no finer precision)."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.min
    return parsed.replace(tzinfo=None, microsecond=0)


# Within the same second: the original request comes first, a takeover precedes the messages
# it affects, and a hand-back follows them.
_SAME_SECOND_ORDER = {"request": -1, "takeover": 0, "turn": 1, "release": 2}


def conversation(rfp: RFPSubmission) -> dict:
    """Client / AI / admin messages in order, plus takeover and hand-back markers."""
    from apps.negotiation_agent.client_session_memory import normalize_session
    from apps.negotiation_agent.views import HUMAN_TAKEOVER_REPLY

    events = list(
        AdminAuditEvent.objects.select_related("actor").filter(
            target_type="rfp",
            target_id=str(rfp.id),
            action__in=("negotiation.takeover", "negotiation.release", "negotiation.message"),
        )
    )
    operator_by_text = {
        (e.payload_json or {}).get("text"): (e.actor.email if e.actor_id else None)
        for e in events
        if e.action == "negotiation.message"
    }
    transcript = normalize_session(rfp.client_session_json).get("transcript", [])
    messages = []
    # The client's first message becomes the request itself, so it isn't in the chat history.
    request_text = (rfp.source_document_text or "").strip()
    if request_text and not any(
        t["role"] == "user" and t["text"].strip()[:200] == request_text[:200] for t in transcript
    ):
        messages.append(
            {"who": "client", "by": None, "text": request_text, "at": rfp.created_at.isoformat(), "_order": "request"}
        )
    previous = None
    for turn in transcript:
        key = (turn["role"], turn["text"], turn["at"])
        if key == previous:
            continue  # the same turn saved twice by two code paths
        previous = key
        text = turn["text"]
        if turn["role"] == "user":
            who, by = "client", None
        elif text in operator_by_text:
            who, by = "admin", operator_by_text[text]
        elif text == HUMAN_TAKEOVER_REPLY:
            who, by = "auto", None
        else:
            who, by = "agent", None
        messages.append({"who": who, "by": by, "text": text, "at": turn["at"], "_order": "turn"})
    for e in events:
        if e.action == "negotiation.message":
            continue
        name = e.actor.email if e.actor_id else "An admin"
        text = (
            f"{name} took over the conversation"
            if e.action == "negotiation.takeover"
            else f"{name} handed the conversation back to the AI agent"
        )
        order = "takeover" if e.action == "negotiation.takeover" else "release"
        messages.append({"who": "system", "by": name, "text": text, "at": e.created_at.isoformat(), "_order": order})
    messages.sort(key=lambda m: (_when(m["at"]), _SAME_SECOND_ORDER[m.pop("_order")]))
    return {
        "rfp_id": str(rfp.id),
        "taken_over": rfp.status == RFPStatus.ESCALATED,
        "messages": messages,
    }
