from django.conf import settings
from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsAdminRole
from apps.dynamic_pricing.models import DynamicPricingQuote, PricingPolicy
from apps.dynamic_pricing.services import FALLBACK_REASON_LABELS, default_property, model_status
from apps.dynamic_pricing.training import train_model
from apps.inventory.models import HistoricalOccupancy, SpaceInventory, VenueProperty
from apps.rfp_debate.models import DebateIterationLog, RFPStatus, RFPSubmission

from . import audit
from .models import AdminAuditEvent
from .serializers import (
    AdminOccupancySerializer,
    AdminPropertySerializer,
    AdminSpaceSerializer,
    PricingPolicySerializer,
)
from .services import AdminConflictError, AdminInputError
from .services import negotiation as negotiation_service
from .services import rfps as rfp_service
from .services.occupancy_import import import_csv
from .services.stats import build_overview, build_telemetry, occupancy_range


def _first_message(detail) -> str:
    if isinstance(detail, dict):
        for value in detail.values():
            return _first_message(value)
    if isinstance(detail, list) and detail:
        return _first_message(detail[0])
    return str(detail)


class AdminErrorsMixin:
    """Every admin endpoint returns {"detail": ...} (+ "errors" for field problems)."""

    def handle_exception(self, exc):
        if isinstance(exc, AdminConflictError):
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        if isinstance(exc, AdminInputError):
            return Response({"detail": str(exc), **exc.extra}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, ValidationError):
            return Response(
                {"detail": _first_message(exc.detail), "errors": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(exc)


class AdminAPIView(AdminErrorsMixin, APIView):
    """Every admin endpoint: ADMIN role only, consistent error bodies."""

    permission_classes = [IsAdminRole]


def _int_param(request, name: str, default: int, *, maximum: int) -> int:
    try:
        return max(1, min(int(request.query_params.get(name, default)), maximum))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- Overview


class OverviewView(AdminAPIView):
    def get(self, request):
        return Response(build_overview())


class TelemetryView(AdminAPIView):
    def get(self, request):
        return Response(build_telemetry())


class AuditListView(AdminAPIView):
    def get(self, request):
        qs = AdminAuditEvent.objects.select_related("actor")
        if request.query_params.get("target_type"):
            qs = qs.filter(target_type=request.query_params["target_type"])
        if request.query_params.get("target_id"):
            qs = qs.filter(target_id=request.query_params["target_id"])
        limit = _int_param(request, "limit", 50, maximum=200)
        return Response([audit.serialize_event(e) for e in qs[:limit]])


# ---------------------------------------------------------------- Module 2: debates


class RFPListView(AdminAPIView):
    def get(self, request):
        status_filter = request.query_params.get("status") or None
        if status_filter and status_filter not in RFPStatus.values:
            raise AdminInputError(f"Unknown status '{status_filter}'.")
        return Response(rfp_service.rfp_list(status=status_filter, q=request.query_params.get("q")))


class RFPDetailView(AdminAPIView):
    def get(self, request, pk):
        rfp = get_object_or_404(RFPSubmission.objects.select_related("client"), pk=pk)
        return Response(rfp_service.rfp_detail(rfp))


class RFPOverrideView(AdminAPIView):
    def post(self, request, pk):
        rfp = get_object_or_404(RFPSubmission, pk=pk)
        result = rfp_service.apply_override(
            rfp, request.data.get("fields") or {}, request.data.get("note") or "", request.user
        )
        return Response(result)


# ---------------------------------------------------------------- Module 3: pricing


class PricingPolicyView(AdminAPIView):
    def get(self, request):
        return Response(PricingPolicySerializer(PricingPolicy.get_solo()).data)

    def put(self, request):
        policy = PricingPolicy.get_solo()
        before = PricingPolicySerializer(policy).data
        serializer = PricingPolicySerializer(policy, data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": _first_message(serializer.errors), "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        policy = serializer.save(updated_by=request.user)
        after = PricingPolicySerializer(policy).data
        changed = {
            k: {"from": before[k], "to": after[k]}
            for k in after
            if k not in ("updated_by", "updated_at") and before[k] != after[k]
        }
        audit.record(request.user, "pricing.policy.update", "policy", policy.pk, changes=changed)
        return Response(after)


class PricingModelView(AdminAPIView):
    def get(self, request):
        return Response(model_status())


class PricingRetrainView(AdminAPIView):
    def post(self, request):
        prop_id = request.data.get("property") if hasattr(request, "data") else None
        prop = VenueProperty.objects.filter(pk=prop_id).first() if prop_id else None
        prop = prop or VenueProperty.objects.order_by("created_at").first()
        if not prop:
            raise AdminInputError("Add a property in Inventory before training the model.")
        try:
            result = train_model(prop)
        except Exception as exc:  # training libs can fail in many ways; report, don't crash
            result = {"status": "error", "detail": f"Training failed: {exc.__class__.__name__}: {exc}"}
        audit.record(
            request.user, "pricing.retrain", "policy", prop.id,
            result=result["status"], version=result.get("version"), metrics=result.get("metrics"),
        )
        code = status.HTTP_500_INTERNAL_SERVER_ERROR if result["status"] == "error" else status.HTTP_200_OK
        return Response(result, status=code)


class QuoteExplanationView(AdminAPIView):
    """Why this price? Every step of the quote, adding up exactly to the stored target and anchor."""

    def get(self, request, pk):
        quote = get_object_or_404(DynamicPricingQuote.objects.select_related("rfp"), pk=pk)
        explanation = quote.explanation_json or {}
        return Response(
            {
                "quote_id": str(quote.id),
                "rfp_id": str(quote.rfp_id),
                "company_name": rfp_service.company_name(quote.rfp),
                "created_at": quote.created_at.isoformat(),
                "engine": quote.engine,
                "model_version": quote.model_version,
                "fallback_reason": quote.fallback_reason,
                "fallback_reason_label": FALLBACK_REASON_LABELS.get(quote.fallback_reason, quote.fallback_reason),
                "inputs": quote.inputs_json or {},
                "steps": explanation.get("steps", []),
                "floor_steps": explanation.get("floor_steps", []),
                "floor": str(quote.walk_away_floor_price),
                "target": str(quote.optimal_target_price),
                "anchor": str(quote.initial_anchor_price),
            }
        )


class PricingQuotesView(AdminAPIView):
    def get(self, request):
        qs = DynamicPricingQuote.objects.select_related("rfp").order_by("-created_at")
        if request.query_params.get("rfp"):
            qs = qs.filter(rfp_id=request.query_params["rfp"])
        return Response([rfp_service.quote_to_dict(q, with_rfp=True) for q in qs[:100]])


# ---------------------------------------------------------------- Module 4: negotiations


class NegotiationListView(AdminAPIView):
    def get(self, request):
        return Response(negotiation_service.negotiation_list())


class NegotiationTakeoverView(AdminAPIView):
    def post(self, request, pk):
        rfp = negotiation_service.takeover(get_object_or_404(RFPSubmission, pk=pk), request.user)
        return Response({"id": str(rfp.id), "status": rfp.status})


class NegotiationReleaseView(AdminAPIView):
    def post(self, request, pk):
        rfp = negotiation_service.release(get_object_or_404(RFPSubmission, pk=pk), request.user)
        return Response({"id": str(rfp.id), "status": rfp.status})


class NegotiationConversationView(AdminAPIView):
    def get(self, request, pk):
        return Response(negotiation_service.conversation(get_object_or_404(RFPSubmission, pk=pk)))


class NegotiationMessageView(AdminAPIView):
    def post(self, request, pk):
        rfp = get_object_or_404(RFPSubmission, pk=pk)
        negotiation_service.send_message(rfp, request.user, request.data.get("text") or "")
        return Response({"ok": True})


# ---------------------------------------------------------------- Module 5: inventory


class AdminViewSetMixin(AdminErrorsMixin):
    permission_classes = [IsAdminRole]
    audit_target = ""

    def perform_create(self, serializer):
        obj = serializer.save()
        audit.record(self.request.user, f"inventory.{self.audit_target}.create", self.audit_target, obj.pk, name=obj.name)

    def perform_update(self, serializer):
        obj = serializer.save()
        audit.record(
            self.request.user,
            f"inventory.{self.audit_target}.update",
            self.audit_target,
            obj.pk,
            changes={k: str(v) for k, v in serializer.validated_data.items()},
        )


class PropertyViewSet(AdminViewSetMixin, viewsets.ModelViewSet):
    serializer_class = AdminPropertySerializer
    queryset = VenueProperty.objects.order_by("name")
    audit_target = "property"

    def destroy(self, request, *args, **kwargs):
        prop = self.get_object()
        if prop.spaces.exists() or prop.occupancy_history.exists():
            return Response(
                {"detail": "Remove this property's spaces and occupancy data before deleting it."},
                status=status.HTTP_409_CONFLICT,
            )
        audit.record(request.user, "inventory.property.delete", "property", prop.pk, name=prop.name)
        prop.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SpaceViewSet(AdminViewSetMixin, viewsets.ModelViewSet):
    serializer_class = AdminSpaceSerializer
    audit_target = "space"

    def get_queryset(self):
        qs = SpaceInventory.objects.select_related("property").order_by("name")
        prop = self.request.query_params.get("property")
        return qs.filter(property_id=prop) if prop else qs

    def destroy(self, request, *args, **kwargs):
        space = self.get_object()
        if space.is_booked:
            return Response(
                {"detail": "This space is booked. Release the booking before deleting it."},
                status=status.HTTP_409_CONFLICT,
            )
        audit.record(request.user, "inventory.space.delete", "space", space.pk, name=space.name)
        space.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        space = self.get_object()
        if not space.is_booked:
            return Response({"detail": "This space isn't booked."}, status=status.HTTP_409_CONFLICT)
        space.is_booked = False
        space.booking_idempotency_key = None
        space.save(update_fields=["is_booked", "booking_idempotency_key"])
        audit.record(request.user, "inventory.space.release", "space", space.pk, name=space.name)
        return Response(AdminSpaceSerializer(space).data)


# ---------------------------------------------------------------- Module 6: occupancy


class OccupancyListView(AdminAPIView):
    """Newest days first (what an admin just imported is what they want to check), max 366 rows."""

    def get(self, request):
        from apps.inventory.models import OccupancySource

        qs = HistoricalOccupancy.objects.order_by("-target_date")
        params = request.query_params
        if params.get("property"):
            qs = qs.filter(property_id=params["property"])
        if params.get("from"):
            qs = qs.filter(target_date__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(target_date__lte=params["to"])
        if params.get("source"):
            if params["source"] not in OccupancySource.values:
                raise AdminInputError(f"Unknown source {params['source']!r}.")
            qs = qs.filter(source=params["source"])
        return Response(AdminOccupancySerializer(qs[:366], many=True).data)


class OccupancyUploadView(AdminAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        prop_id = request.data.get("property")
        prop = VenueProperty.objects.filter(pk=prop_id).first() if prop_id else VenueProperty.objects.first()
        if prop is None:
            raise AdminInputError("Choose a property for this data.")
        report = import_csv(request.FILES.get("file"), prop)
        audit.record(
            request.user,
            "occupancy.upload",
            "occupancy",
            prop.pk,
            created=report["created"],
            updated=report["updated"],
            skipped=report["skipped"],
        )
        return Response(report)


class OccupancySummaryView(AdminAPIView):
    def get(self, request):
        from apps.dynamic_pricing.training import data_counts

        occ = occupancy_range()
        counts = data_counts(default_property())
        return Response(
            {
                "engine": settings.DB_ENGINE_MODE,
                "vendor": connection.vendor,
                "tables": {
                    "rfp": RFPSubmission.objects.count(),
                    "quotes": DynamicPricingQuote.objects.count(),
                    "occupancy": occ["rows"],
                    "spaces": SpaceInventory.objects.count(),
                },
                "occupancy_range": {"from": occ["from"], "to": occ["to"]},
                "by_source": {k: counts[k] for k in ("imported", "demo", "manual", "generated")},
            }
        )


# ---------------------------------------------------------------- Original endpoints (kept)


class DebateObservatoryView(AdminAPIView):
    def get(self, request):
        logs = DebateIterationLog.objects.select_related("rfp").order_by("-id")[:50]
        data = [
            {
                "rfp_id": str(log.rfp_id),
                "iteration": log.iteration_number,
                "consensus": log.arbiter_consensus_score,
                "flags": log.discrepancy_flags_json,
                "duration_ms": log.duration_ms,
            }
            for log in logs
        ]
        return Response({"debates": data})


class SLATelemetryView(AdminAPIView):
    def get(self, request):
        rfps = RFPSubmission.objects.exclude(sla_started_at__isnull=True)[:100]
        rows = []
        for rfp in rfps:
            duration = None
            if rfp.sla_started_at and rfp.sla_completed_at:
                duration = (rfp.sla_completed_at - rfp.sla_started_at).total_seconds()
            rows.append({"rfp_id": str(rfp.id), "status": rfp.status, "duration_seconds": duration})
        return Response({"sla": rows})


class OccupancyIngestView(AdminAPIView):
    parser_classes = [JSONParser]

    def post(self, request):
        prop = VenueProperty.objects.first()
        if prop is None:
            raise AdminInputError("Add a property before importing occupancy.")
        rows = request.data.get("rows", [])
        created = 0
        for row in rows:
            HistoricalOccupancy.objects.update_or_create(
                property=prop,
                target_date=row["target_date"],
                defaults={
                    "room_occupancy_pct": row.get("room_occupancy_pct", 0.7),
                    "hall_utilization_pct": row.get("hall_utilization_pct", 0.5),
                    "adr": row.get("adr", 200),
                    "revpar": row.get("revpar", 150),
                },
            )
            created += 1
        return Response({"imported": created})


class ModuleStubView(AdminAPIView):
    def get(self, request):
        return Response({"modules": list(range(1, 8)), "status": "ok"})
