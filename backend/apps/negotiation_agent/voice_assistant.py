"""Live negotiation voice replies via Muse Spark 1.3 + autonomous scenario scripts."""
from __future__ import annotations

import logging

from django.conf import settings

from apps.guardrails.validators import validate_negotiation_text
from apps.rfp_debate.meta_client import MetaModelAPIError, MetaModelClient
from apps.rfp_debate.models import RFPSubmission

from .client_turn_router import is_social_greeting
from .voice_scenario import (
    generate_voice_assistant_reply as scenario_reply,
    progressive_status_messages,
    quick_voice_ack,
    rfp_has_meaningful_cards,
)
from .availability_inquiry import try_availability_response
from .client_inquiry import try_client_planning_response
from .voice_intake import persist_intake_reply, record_availability_window, try_voice_intake_followup
from .voice_intake_llm import try_llm_intake_reply
from .voice_room_block_gate import try_room_block_capacity_reply
from .voice_dates import voice_date_context_line
from .client_session_memory import (
    build_agent_context_block,
    record_assistant_reply,
    record_voice_turn,
)
from .client_turn_handoff import apply_llm_turn_handoff, client_message_signals_repeat_frustration
from .muse_client import client_assistant_model_id, client_assistant_reasoning_effort

logger = logging.getLogger(__name__)


def _persist_assistant_reply(rfp: RFPSubmission | None, reply: str) -> None:
    if not rfp or not (reply or "").strip():
        return
    record_assistant_reply(rfp, reply)
    rfp.save(update_fields=["client_session_json", "updated_at"])


def _persist_assistant_reply_with_handoff(
    rfp: RFPSubmission | None,
    reply: str,
    *,
    llm_handoff: dict | None = None,
) -> None:
    if not rfp or not (reply or "").strip():
        return
    record_assistant_reply(rfp, reply)
    if llm_handoff:
        apply_llm_turn_handoff(rfp, llm_handoff)
    rfp.save(update_fields=["client_session_json", "updated_at"])


def generate_voice_assistant_reply(message: str, *, rfp_status: str | None = None) -> str:
    return generate_voice_assistant_reply_for_rfp(message, rfp=None, rfp_status=rfp_status)


def generate_voice_assistant_reply_for_rfp(
    message: str,
    *,
    rfp: RFPSubmission | None,
    rfp_status: str | None = None,
) -> str:
    validate_negotiation_text(message)
    cleaned = message.strip()
    if rfp and cleaned:
        record_voice_turn(rfp, cleaned)
        rfp.save(update_fields=["client_session_json", "updated_at"])
        from .client_group_context import ensure_group_size_on_cards

        ensure_group_size_on_cards(rfp)

    if rfp and client_message_signals_repeat_frustration(cleaned):
        from .client_turn_handoff import spoken_recap_from_handoff

        recap = spoken_recap_from_handoff(rfp)
        _persist_assistant_reply(rfp, recap)
        return recap

    if is_social_greeting(cleaned):
        scripted = scenario_reply(cleaned, rfp=rfp)
        _persist_assistant_reply(rfp, scripted)
        return scripted

    intake_reply = try_voice_intake_followup(rfp, cleaned)
    if intake_reply:
        persist_intake_reply(rfp, intake_reply)
        rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        return intake_reply

    block_reply = try_room_block_capacity_reply(rfp, cleaned)
    if block_reply:
        persist_intake_reply(rfp, block_reply)
        if rfp:
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        return block_reply

    planning = try_client_planning_response(rfp, cleaned)
    if planning:
        spoken, ui = planning
        if rfp:
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        _persist_assistant_reply(rfp, spoken)
        return spoken

    avail = try_availability_response(cleaned)
    if avail:
        spoken, ui = avail
        if rfp and ui:
            record_availability_window(rfp, ui)
        _persist_assistant_reply(rfp, spoken)
        if rfp:
            rfp.save(update_fields=["client_session_json", "updated_at"])
        return spoken

    if rfp:
        from .voice_card_updates import VoiceDateValidationError, apply_voice_message_to_cards

        try:
            card_patch = apply_voice_message_to_cards(str(rfp.id), cleaned)
        except VoiceDateValidationError as exc:
            _persist_assistant_reply(rfp, exc.message)
            return exc.message
        except Exception as exc:
            from apps.core.exceptions import CardMutationValidationError

            if isinstance(exc, CardMutationValidationError):
                _persist_assistant_reply(rfp, str(exc))
                return str(exc)
            raise
        if card_patch:
            rfp.refresh_from_db()
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
            from .client_session_memory import build_card_mutation_ack

            ack = build_card_mutation_ack(card_patch, rfp.active_ui_cards_json or {})
            _persist_assistant_reply(rfp, ack)
            return ack

    llm_intake = try_llm_intake_reply(rfp, cleaned) if rfp else None
    if llm_intake:
        persist_intake_reply(rfp, llm_intake)
        if rfp:
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        return llm_intake

    scripted = scenario_reply(cleaned, rfp=rfp)

    correction_hint = any(
        w in cleaned.lower()
        for w in (
            "headcount",
            "guest",
            "people",
            "night",
            "nights",
            "not ",
            "actually",
            "arriv",
            "depart",
            "check-in",
            "check in",
            "check-out",
            "check out",
            "tuesday",
            "monday",
            "wednesday",
            "thursday",
            "friday",
            "sunday",
            "participant",
            "participants",
            "several room",
            "multiple room",
            "next week",
            "what kind",
        )
    )
    if rfp and (rfp_has_meaningful_cards(rfp) or correction_hint):
        _persist_assistant_reply(rfp, scripted)
        return scripted

    if settings.USE_FIXTURE_DEBATE or not settings.META_MODEL_API_KEY:
        _persist_assistant_reply(rfp, scripted)
        return scripted

    if cleaned.lower() in {"hi", "hello", "hey", "yo"}:
        _persist_assistant_reply(rfp, scripted)
        return scripted

    context = build_agent_context_block(rfp)
    if context:
        context = context + "\n"
    context += (
        f"{voice_date_context_line()}\n"
        f"RFP session status: {rfp_status or (rfp.status if rfp else 'unknown')}."
    )
    client = MetaModelClient()
    try:
        raw = client.complete_json(
            model_id=client_assistant_model_id(),
            reasoning_effort=client_assistant_reasoning_effort(),
            system_prompt=(
                voice_date_context_line() + " "
                "You are a professional hospitality sales assistant on a voice call with a client. "
                "Use warm, concise language. Never mention internal tools, AI models, agents, "
                "debates, verification pipelines, floor prices, anchor pricing jargon, or card UI mechanics. "
                "Offer help with dates, room block, meeting space, quotes, approval, or negotiation. "
                "Do not mention venue maps or floor plans — those belong in Design Studio proposals only. "
                'Return JSON with keys "reply" (one or two short spoken sentences) and '
                '"turn_handoff" (object with gathered, still_needed, ask_next, optional '
                "notes_for_next_turn). Use NEXT TURN HANDOFF and session memory — never "
                "re-ask fields already in gathered."
            ),
            user_content=f"{context}\nUser: {cleaned}",
            fixture_kind="voice_reply",
        )
    except (MetaModelAPIError, Exception) as exc:
        logger.debug("Voice Muse reply fallback to script: %s", exc)
        _persist_assistant_reply(rfp, scripted)
        return scripted
    if isinstance(raw, dict):
        reply = raw.get("reply") or raw.get("message")
        llm_handoff = raw.get("turn_handoff") if isinstance(raw.get("turn_handoff"), dict) else None
        if isinstance(reply, str) and reply.strip():
            lower = reply.lower()
            if "update" in lower and "card" in lower:
                _persist_assistant_reply(rfp, scripted)
                return scripted
            if "manual" in lower and "card" in lower:
                _persist_assistant_reply(rfp, scripted)
                return scripted
            final = reply.strip()
            _persist_assistant_reply_with_handoff(rfp, final, llm_handoff=llm_handoff)
            return final
    _persist_assistant_reply(rfp, scripted)
    return scripted


def iter_voice_assistant_stream(
    message: str,
    *,
    rfp: RFPSubmission | None,
    rfp_status: str | None = None,
):
    """SSE-friendly events: status, token, done."""
    validate_negotiation_text(message)
    cleaned = message.strip()
    if rfp and cleaned:
        record_voice_turn(rfp, cleaned)
        rfp.save(update_fields=["client_session_json", "updated_at"])
        from .client_group_context import ensure_group_size_on_cards

        ensure_group_size_on_cards(rfp)

    if rfp and client_message_signals_repeat_frustration(cleaned):
        from .client_turn_handoff import spoken_recap_from_handoff

        recap = spoken_recap_from_handoff(rfp)
        _persist_assistant_reply(rfp, recap)
        yield {"type": "done", "reply": recap}
        return

    if is_social_greeting(cleaned):
        scripted = scenario_reply(cleaned, rfp=rfp)
        _persist_assistant_reply(rfp, scripted)
        yield {"type": "done", "reply": scripted}
        return

    intake_reply = try_voice_intake_followup(rfp, cleaned)
    if intake_reply:
        persist_intake_reply(rfp, intake_reply)
        rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        yield {"type": "status", "text": "Noting your arrival date…"}
        yield {"type": "done", "reply": intake_reply}
        return

    block_reply = try_room_block_capacity_reply(rfp, cleaned)
    if block_reply:
        persist_intake_reply(rfp, block_reply)
        if rfp:
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        yield {"type": "status", "text": "Checking room inventory against your block…"}
        yield {"type": "done", "reply": block_reply}
        return

    planning = try_client_planning_response(rfp, cleaned)
    if planning:
        spoken, ui = planning
        if rfp:
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        yield {"type": "status", "text": "Checking your group size and room inventory…"}
        _persist_assistant_reply(rfp, spoken)
        done_payload: dict = {"reply": spoken}
        if ui:
            done_payload["ui_component"] = ui
        yield {"type": "done", **done_payload}
        return

    avail = try_availability_response(cleaned)
    if avail:
        spoken, ui = avail
        if rfp and ui:
            record_availability_window(rfp, ui)
            rfp.save(update_fields=["client_session_json", "updated_at"])
        yield {"type": "status", "text": "Checking room availability for next week…"}
        _persist_assistant_reply(rfp, spoken)
        done_payload: dict = {"reply": spoken}
        if ui:
            done_payload["ui_component"] = ui
        yield {"type": "done", **done_payload}
        return

    if rfp:
        from .voice_card_updates import VoiceDateValidationError, apply_voice_message_to_cards

        try:
            card_patch = apply_voice_message_to_cards(str(rfp.id), cleaned)
        except VoiceDateValidationError as exc:
            _persist_assistant_reply(rfp, exc.message)
            yield {"type": "done", "reply": exc.message}
            return
        except Exception as exc:
            from apps.core.exceptions import CardMutationValidationError

            if isinstance(exc, CardMutationValidationError):
                _persist_assistant_reply(rfp, str(exc))
                yield {"type": "done", "reply": str(exc)}
                return
            raise
        if card_patch:
            rfp.refresh_from_db()
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
            from .client_session_memory import build_card_mutation_ack

            ack = build_card_mutation_ack(card_patch, rfp.active_ui_cards_json or {})
            _persist_assistant_reply(rfp, ack)
            yield {"type": "done", "reply": ack}
            return

    llm_intake = try_llm_intake_reply(rfp, cleaned) if rfp else None
    if llm_intake:
        persist_intake_reply(rfp, llm_intake)
        if rfp:
            rfp.save(update_fields=["client_session_json", "active_ui_cards_json", "updated_at"])
        yield {"type": "done", "reply": llm_intake}
        return

    yield {"type": "status", "text": quick_voice_ack(cleaned)}

    for line in progressive_status_messages(cleaned, rfp=rfp):
        yield {"type": "status", "text": line}

    scripted = scenario_reply(cleaned, rfp=rfp)
    correction_hint = any(
        w in cleaned.lower()
        for w in (
            "headcount",
            "guest",
            "people",
            "night",
            "nights",
            "not ",
            "actually",
            "arriv",
            "depart",
            "check-in",
            "check in",
            "check-out",
            "check out",
            "tuesday",
            "monday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "participant",
            "participants",
            "several room",
            "multiple room",
            "next week",
            "what kind",
        )
    )
    use_scripted_only = (
        (rfp and rfp_has_meaningful_cards(rfp))
        or (rfp and correction_hint)
        or settings.USE_FIXTURE_DEBATE
        or not settings.META_MODEL_API_KEY
        or cleaned.lower() in {"hi", "hello", "hey", "yo"}
    )

    if use_scripted_only:
        _persist_assistant_reply(rfp, scripted)
        yield {"type": "done", "reply": scripted}
        return

    context = build_agent_context_block(rfp)
    if context:
        context = context + "\n"
    context += (
        f"{voice_date_context_line()}\n"
        f"RFP session status: {rfp_status or (rfp.status if rfp else 'unknown')}."
    )
    system_prompt = (
        voice_date_context_line() + " "
        "You are a professional hospitality sales assistant on a live voice call. "
        "Reply in one or two short spoken sentences. Warm and concise. "
        "Never mention AI, models, agents, debates, floor prices, card UI mechanics, "
        "venue maps, or floor plans (Design Studio only)."
    )
    user_content = f"{context}\nUser: {cleaned}"
    client = MetaModelClient()
    buffer = ""
    try:
        for delta in client.stream_text(
            model_id=client_assistant_model_id(),
            system_prompt=system_prompt,
            user_content=user_content,
            reasoning_effort=client_assistant_reasoning_effort(),
        ):
            buffer += delta
            yield {"type": "token", "text": delta}
    except Exception:
        _persist_assistant_reply(rfp, scripted)
        yield {"type": "done", "reply": scripted}
        return

    reply = buffer.strip() or scripted
    lower = reply.lower()
    if "update" in lower and "card" in lower:
        reply = scripted
    elif "manual" in lower and "card" in lower:
        reply = scripted
    _persist_assistant_reply(rfp, reply)
    done_payload: dict = {"reply": reply}
    if rfp:
        from apps.negotiation_agent.client_session_memory import normalize_session

        handoff = normalize_session(rfp.client_session_json).get("turn_handoff")
        if handoff:
            done_payload["turn_handoff"] = handoff
    yield {"type": "done", **done_payload}
