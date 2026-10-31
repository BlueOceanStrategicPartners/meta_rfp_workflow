from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from celery import shared_task
from django.utils import timezone

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
    cards = dict(rfp.active_ui_cards_json or {})
    cards["live_quote"] = {
        "anchor_price": float(quote.initial_anchor_price),
        "floor_price": float(quote.walk_away_floor_price),
        "target_price": float(quote.optimal_target_price),
    }
    rfp.active_ui_cards_json = cards
    rfp.status = RFPStatus.NEGOTIATING
    rfp.save(update_fields=["active_ui_cards_json", "status", "updated_at"])


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
            {"error": f"Debate used fallback extraction: {exc.__class__.__name__}"},
        )

    rfp.refresh_from_db()
    normalize_cards_for_ui(rfp)

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
        "debate_progress",
        {"status": rfp.status, "consensus": not partial},
    )
    utterance = build_voice_intro_for_rfp(rfp, partial=partial)
    if utterance:
        broadcast_rfp(str(rfp.id), "agent_utterance", {"text": utterance})
    return {
        "rfp_id": str(rfp.id),
        "partial": partial,
        "voice_intro": utterance,
    }
