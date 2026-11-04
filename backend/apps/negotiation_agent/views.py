from decimal import Decimal

import json

from django.http import StreamingHttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsClientRole
from apps.core.exceptions import FloorPriceBreachAttemptError
from apps.dynamic_pricing.models import DynamicPricingQuote
from apps.guardrails.validators import enforce_floor_price, validate_negotiation_text
from apps.inventory.locking import lock_zone_for_booking
from apps.rfp_debate.models import RFPStatus, RFPSubmission

from .negotiation_renderers import ServerSentEventsRenderer
from .voice_assistant import generate_voice_assistant_reply_for_rfp, iter_voice_assistant_stream
from .availability_inquiry import try_availability_response


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


HUMAN_TAKEOVER_REPLY = "A member of our team has joined and will reply shortly."


def _is_human_takeover(rfp: RFPSubmission | None) -> bool:
    """While an admin has taken over (ESCALATED), the assistant stays silent."""
    return bool(rfp and rfp.status == RFPStatus.ESCALATED)


def _ensure_reply_saved(rfp: RFPSubmission, reply: str | None) -> None:
    """Some streamed reply paths don't persist the final text; save it once so the admin conversation is complete."""
    from .client_session_memory import normalize_session, record_assistant_reply

    text = (reply or "").strip()
    if not text:
        return
    rfp.refresh_from_db(fields=["client_session_json"])
    transcript = normalize_session(rfp.client_session_json).get("transcript") or []
    if transcript and transcript[-1]["role"] == "assistant" and transcript[-1]["text"] == text[:2000]:
        return
    record_assistant_reply(rfp, text)
    rfp.save(update_fields=["client_session_json", "updated_at"])


def _record_takeover_turn(rfp: RFPSubmission, message: str) -> None:
    """Keep the client's words in the conversation history so the admin can read them."""
    from .client_session_memory import record_assistant_reply, record_voice_turn

    if message.strip():
        record_voice_turn(rfp, message.strip())
    record_assistant_reply(rfp, HUMAN_TAKEOVER_REPLY)
    rfp.save(update_fields=["client_session_json", "updated_at"])


class VoiceAssistantChatView(APIView):
    """Spark-driven assistant text for SeamlessM4T v2 playback (single reply per turn)."""

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        message = request.data.get("message", "")
        rfp_id = request.data.get("rfp_id")
        rfp = None
        if rfp_id:
            rfp = RFPSubmission.objects.filter(pk=rfp_id).first()
        if _is_human_takeover(rfp):
            _record_takeover_turn(rfp, message)
            return Response({"reply": HUMAN_TAKEOVER_REPLY, "human_takeover": True})
        try:
            if rfp and message.strip():
                from .client_session_memory import record_voice_turn

                record_voice_turn(rfp, message.strip())
                rfp.save(update_fields=["client_session_json", "updated_at"])
            avail = try_availability_response(message)
            if avail:
                spoken, ui = avail
                from .client_session_memory import record_assistant_reply

                if rfp:
                    record_assistant_reply(rfp, spoken)
                    rfp.save(update_fields=["client_session_json", "updated_at"])
                reply_payload = {"reply": spoken}
                if ui:
                    reply_payload["ui_component"] = ui
                return Response(reply_payload)
            reply = generate_voice_assistant_reply_for_rfp(
                message,
                rfp=rfp,
                rfp_status=rfp.status if rfp else None,
            )
        except Exception as exc:
            if isinstance(exc, FloorPriceBreachAttemptError):
                return Response({"reply": "I can't process that request.", "blocked": True}, status=400)
            raise
        return Response({"reply": reply})


class VoiceAssistantChatStreamView(APIView):
    """Progressive SSE: status lines, streamed tokens, final reply."""

    permission_classes = []
    authentication_classes = []
    renderer_classes = [ServerSentEventsRenderer]

    def post(self, request):
        message = request.data.get("message", "")
        rfp_id = request.data.get("rfp_id")
        rfp = None
        if rfp_id:
            rfp = RFPSubmission.objects.filter(pk=rfp_id).first()

        taken_over = _is_human_takeover(rfp)
        if taken_over:
            _record_takeover_turn(rfp, message)

        def event_stream():
            if taken_over:
                yield _sse("done", {"reply": HUMAN_TAKEOVER_REPLY, "human_takeover": True})
                return
            try:
                for item in iter_voice_assistant_stream(
                    message,
                    rfp=rfp,
                    rfp_status=rfp.status if rfp else None,
                ):
                    if item["type"] == "done" and rfp is not None:
                        _ensure_reply_saved(rfp, item.get("reply"))
                    yield _sse(item["type"], {k: v for k, v in item.items() if k != "type"})
            except FloorPriceBreachAttemptError:
                yield _sse("done", {"reply": "I can't process that request.", "blocked": True})
            except Exception as exc:
                yield _sse("error", {"message": str(exc)})

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class NegotiationOfferView(APIView):
    permission_classes = [IsClientRole]

    def post(self, request):
        validate_negotiation_text(request.data.get("message", ""))
        rfp = RFPSubmission.objects.get(pk=request.data["rfp_id"], client=request.user)
        quote = DynamicPricingQuote.objects.filter(rfp=rfp).order_by("-created_at").first()
        if not quote:
            return Response({"detail": "No quote"}, status=400)
        offer = Decimal(str(request.data.get("offer_price", 0)))
        try:
            enforce_floor_price(offer, quote.walk_away_floor_price)
        except FloorPriceBreachAttemptError as exc:
            return Response({"ok": False, "error": str(exc)}, status=400)
        quote.agreed_final_price = offer
        quote.save(update_fields=["agreed_final_price"])
        return Response({"ok": True, "agreed_final_price": str(offer)})


class BookRFPView(APIView):
    permission_classes = [IsClientRole]

    def post(self, request):
        rfp = RFPSubmission.objects.get(pk=request.data["rfp_id"], client=request.user)
        zone_id = request.data.get("zone_id")
        idempotency_key = request.data.get("idempotency_key", str(rfp.id))
        if zone_id:
            from apps.core.exceptions import InventoryLockConflictError

            try:
                lock_zone_for_booking(zone_id, idempotency_key)
            except InventoryLockConflictError as exc:
                return Response({"ok": False, "error": str(exc)}, status=409)
        rfp.status = RFPStatus.BOOKED
        rfp.save(update_fields=["status"])
        return Response({"ok": True, "status": rfp.status})
