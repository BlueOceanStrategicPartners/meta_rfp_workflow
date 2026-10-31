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

from .voice_assistant import generate_voice_assistant_reply_for_rfp, iter_voice_assistant_stream


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


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
        try:
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

    def post(self, request):
        message = request.data.get("message", "")
        rfp_id = request.data.get("rfp_id")
        rfp = None
        if rfp_id:
            rfp = RFPSubmission.objects.filter(pk=rfp_id).first()

        def event_stream():
            try:
                for item in iter_voice_assistant_stream(
                    message,
                    rfp=rfp,
                    rfp_status=rfp.status if rfp else None,
                ):
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
