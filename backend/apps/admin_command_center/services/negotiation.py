"""Live negotiation monitor: list, human takeover, hand back, operator messages."""
from __future__ import annotations

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
    audit.record(actor, "negotiation.message", "rfp", rfp.id, text=clean)
