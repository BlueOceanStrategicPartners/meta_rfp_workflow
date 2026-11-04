"""Optional LLM tier when deterministic intake gates do not match (ambiguous ASR)."""
from __future__ import annotations

import logging

from django.conf import settings

from apps.rfp_debate.meta_client import MetaModelAPIError, MetaModelClient
from apps.rfp_debate.models import RFPSubmission

from .muse_client import client_assistant_model_id, client_assistant_reasoning_effort
from .voice_intake_apply import apply_intake_classification_to_cards
from .voice_intake_gates import build_llm_intake_context
from .voice_prompts import INTAKE_CLASSIFIER_SYSTEM, intake_classifier_user

logger = logging.getLogger(__name__)


def try_llm_intake_reply(rfp: RFPSubmission, message: str, *, rooms_free: int | None = None) -> str | None:
    """
    Single JSON classification call — used only when gates + planning did not handle the turn.
    Returns high-confidence reply or None (caller falls back to scenario/LLM stream).
    """
    if settings.USE_FIXTURE_DEBATE or not settings.META_MODEL_API_KEY:
        return None
    cleaned = (message or "").strip()
    if not cleaned or len(cleaned) < 12:
        return None

    context = build_llm_intake_context(rfp)
    client = MetaModelClient()
    try:
        raw = client.complete_json(
            model_id=client_assistant_model_id(),
            reasoning_effort=client_assistant_reasoning_effort(),
            system_prompt=INTAKE_CLASSIFIER_SYSTEM,
            user_content=intake_classifier_user(context, cleaned, rooms_free=rooms_free),
            fixture_kind="voice_intake_classify",
        )
    except (MetaModelAPIError, Exception) as exc:
        logger.debug("Intake LLM gate skipped: %s", exc)
        return None

    if not isinstance(raw, dict):
        return None
    try:
        confidence = float(raw.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    reply = raw.get("reply")
    if confidence < 0.85 or not isinstance(reply, str) or not reply.strip():
        return None
    if apply_intake_classification_to_cards(rfp, raw):
        rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
    return reply.strip()
