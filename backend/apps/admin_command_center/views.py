from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsAdminRole
from apps.rfp_debate.models import DebateIterationLog, RFPSubmission


class DebateObservatoryView(APIView):
    permission_classes = [IsAdminRole]

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


class SLATelemetryView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        rfps = RFPSubmission.objects.exclude(sla_started_at__isnull=True)[:100]
        rows = []
        for rfp in rfps:
            duration = None
            if rfp.sla_started_at and rfp.sla_completed_at:
                duration = (rfp.sla_completed_at - rfp.sla_started_at).total_seconds()
            rows.append(
                {
                    "rfp_id": str(rfp.id),
                    "status": rfp.status,
                    "duration_seconds": duration,
                }
            )
        return Response({"sla": rows})


class NegotiationMonitorView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        rfps = RFPSubmission.objects.filter(status="NEGOTIATING")[:20]
        return Response({"active": [{"id": str(r.id)} for r in rfps]})


class OccupancyIngestView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request):
        from apps.inventory.models import HistoricalOccupancy, VenueProperty

        prop = VenueProperty.objects.first()
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


class HumanOverrideDebateView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, rfp_id):
        rfp = RFPSubmission.objects.get(pk=rfp_id)
        rfp.status = "AWAITING_USER_CARD_EDIT"
        rfp.save(update_fields=["status"])
        return Response({"status": rfp.status})


class ModuleStubView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response({"modules": list(range(1, 8)), "status": "ok"})
