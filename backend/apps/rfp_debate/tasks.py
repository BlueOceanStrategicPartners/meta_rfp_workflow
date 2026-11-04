from __future__ import annotations

import threading

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from celery import shared_task
from django.utils import timezone

from django.conf import settings

from apps.core.exceptions import MaxDebateIterationsExceededError
from apps.dynamic_pricing.services import compute_dynamic_quote
from apps.rfp_debate.models import RFPStatus

from .arbiter_orchestrator import ArbiterOrchestrator
from .card_normalize import normalize_cards_for_ui
from .models import RFPSubmission
from .voice_intro import build_voice_intro_for_rfp


def broadcast_rfp(session_id: str, message_type: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"rfp_{session_id}",
        {"type": "rfp.message", "message_type": message_type, "payload": payload},
    )


def _apply_quote_to_cards(rfp: RFPSubmission, quote) -> None:
    from apps.dynamic_pricing.services import client_quote_card

    cards = dict(rfp.active_ui_cards_json or {})
    # The client sees the opening offer only; floor and target stay server-side (admin only).
    cards["live_quote"] = client_quote_card(quote)
    rfp.active_ui_cards_json = cards
    rfp.status = RFPStatus.NEGOTIATING
    update_fields = ["active_ui_cards_json", "status", "updated_at"]
    if not rfp.sla_completed_at:
        # SLA clock stops when the client first sees a priced package.
        rfp.sla_completed_at = timezone.now()
        update_fields.append("sla_completed_at")
    rfp.save(update_fields=update_fields)


def enqueue_debate_pipeline(rfp_id: str) -> None:
    """
    Local dev uses CELERY_TASK_ALWAYS_EAGER, which would block HTTP until debate finishes.
    Run the pipeline in a daemon thread so POST /api/rfp/ returns immediately.
    """
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        threading.Thread(
            target=run_debate_pipeline,
            args=(rfp_id,),
            daemon=True,
            name=f"debate-{rfp_id[:8]}",
        ).start()
        return
    run_debate_pipeline.delay(rfp_id)


@shared_task
def run_debate_pipeline(rfp_id: str) -> dict:
    rfp = RFPSubmission.objects.get(pk=rfp_id)
    if not rfp.sla_started_at:
        rfp.sla_started_at = timezone.now()
        rfp.save(update_fields=["sla_started_at"])
    rfp.status = RFPStatus.EXTRACTING
    rfp.save(update_fields=["status"])
    broadcast_rfp(str(rfp.id), "debate_progress", {"status": rfp.status, "phase": "extracting"})
    orchestrator = ArbiterOrchestrator()
    partial = False
    try:
        orchestrator.run_debate(rfp)
    except MaxDebateIterationsExceededError:
        partial = True
        rfp.refresh_from_db()
    except Exception as exc:
        partial = True
        rfp.refresh_from_db()
        broadcast_rfp(
            str(rfp.id),
            "validation_error",
            {"error": f"The AI couldn't read this request automatically ({exc.__class__.__name__}). Please check the details on the cards."},
        )

    rfp.refresh_from_db()
    normalize_cards_for_ui(rfp)

    from apps.negotiation_agent.client_session_memory import sync_clarifications_from_cards

    sync_clarifications_from_cards(rfp)
    rfp.save(update_fields=["client_session_json"])

    overview = (rfp.active_ui_cards_json or {}).get("event_overview") or {}
    if overview.get("company_name"):
        try:
            quote = compute_dynamic_quote(rfp)
            _apply_quote_to_cards(rfp, quote)
        except Exception:
            rfp.refresh_from_db()

    broadcast_rfp(
        str(rfp.id),
        "cards_patch",
        {"cards": rfp.active_ui_cards_json, "partial_consensus": partial},
    )
    broadcast_rfp(
        str(rfp.id),
        "client_session_patch",
        {"session": rfp.client_session_json},
    )
    broadcast_rfp(
        str(rfp.id),
        "debate_progress",
        {"status": rfp.status, "consensus": not partial},
    )
    utterance = build_voice_intro_for_rfp(rfp, partial=partial)
    if utterance:
        broadcast_rfp(str(rfp.id), "agent_utterance", {"text": utterance})
        # Keep the spoken summary in the conversation history (the admin reads it on takeover).
        from apps.negotiation_agent.client_session_memory import record_assistant_reply

        rfp.refresh_from_db(fields=["client_session_json"])
        record_assistant_reply(rfp, utterance)
        rfp.save(update_fields=["client_session_json"])
    return {
        "rfp_id": str(rfp.id),
        "partial": partial,
        "voice_intro": utterance,
    }
