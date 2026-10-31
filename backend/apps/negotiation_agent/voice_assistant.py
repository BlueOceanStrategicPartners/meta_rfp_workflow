"""Live negotiation voice replies via Muse Spark 1.3 + autonomous scenario scripts."""
from __future__ import annotations

from django.conf import settings

from apps.guardrails.validators import validate_negotiation_text
from apps.rfp_debate.meta_client import MetaModelClient
from apps.rfp_debate.models import RFPSubmission

from .voice_scenario import (
    generate_voice_assistant_reply as scenario_reply,
    progressive_status_messages,
    quick_voice_ack,
    rfp_has_meaningful_cards,
)
from .voice_dates import voice_date_context_line


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
        )
    )
    if rfp and (rfp_has_meaningful_cards(rfp) or correction_hint):
        return scripted

    if settings.USE_FIXTURE_DEBATE or not settings.META_MODEL_API_KEY:
        return scripted

    if cleaned.lower() in {"hi", "hello", "hey", "yo"}:
        return scripted

    context = (
        f"{voice_date_context_line()}\n"
        f"RFP session status: {rfp_status or (rfp.status if rfp else 'unknown')}."
    )
    client = MetaModelClient()
    try:
        raw = client.complete_json(
            model_id=settings.META_MODEL_SPARK,
            system_prompt=(
                voice_date_context_line() + " "
                "You are a professional hospitality sales assistant on a voice call with a client. "
                "Use warm, concise language. Never mention internal tools, AI models, agents, "
                "debates, verification pipelines, floor prices, anchor pricing jargon, or card UI mechanics. "
                "Offer help with dates, room block, meeting space, quotes, venue map, approval, or negotiation. "
                'JSON only: {"reply": "..."} with one or two short spoken sentences.'
            ),
            user_content=f"{context}\nUser: {cleaned}",
        )
    except Exception:
        return scripted
    if isinstance(raw, dict):
        reply = raw.get("reply") or raw.get("message")
        if isinstance(reply, str) and reply.strip():
            lower = reply.lower()
            if "update" in lower and "card" in lower:
                return scripted
            if "manual" in lower and "card" in lower:
                return scripted
            return reply.strip()
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
        for word in scripted.split():
            yield {"type": "token", "text": word + " "}
        yield {"type": "done", "reply": scripted}
        return

    context = (
        f"{voice_date_context_line()}\n"
        f"RFP session status: {rfp_status or (rfp.status if rfp else 'unknown')}."
    )
    system_prompt = (
        voice_date_context_line() + " "
        "You are a professional hospitality sales assistant on a live voice call. "
        "Reply in one or two short spoken sentences. Warm and concise. "
        "Never mention AI, models, agents, debates, floor prices, or card UI mechanics."
    )
    user_content = f"{context}\nUser: {cleaned}"
    client = MetaModelClient()
    buffer = ""
    try:
        for delta in client.stream_text(
            model_id=settings.META_MODEL_SPARK,
            system_prompt=system_prompt,
            user_content=user_content,
        ):
            buffer += delta
            yield {"type": "token", "text": delta}
    except Exception:
        for word in scripted.split():
            yield {"type": "token", "text": word + " "}
        yield {"type": "done", "reply": scripted}
        return

    reply = buffer.strip() or scripted
    lower = reply.lower()
    if "update" in lower and "card" in lower:
        reply = scripted
    elif "manual" in lower and "card" in lower:
        reply = scripted
    yield {"type": "done", "reply": reply}
