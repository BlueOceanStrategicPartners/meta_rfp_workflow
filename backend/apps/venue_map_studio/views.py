from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsAdminRole
from apps.core.exceptions import MapVectorizationFallbackHandler
from apps.inventory.models import InteractiveVenueMap, VenueMapZone
from apps.inventory.serializers import SpaceInventorySerializer

from .pipeline import vectorize_map
from .serializers import VenueMapSerializer, VenueMapZoneSerializer


class VenueMapListCreateView(generics.ListCreateAPIView):
    queryset = InteractiveVenueMap.objects.all()
    serializer_class = VenueMapSerializer
    permission_classes = [IsAdminRole]


class VenueMapVectorizeView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        venue_map = InteractiveVenueMap.objects.get(pk=pk)
        try:
            vectorize_map(venue_map)
            return Response({"status": "ok", "fallback": False})
        except MapVectorizationFallbackHandler as exc:
            return Response(
                {"status": "fallback", "message": str(exc), "editor_enabled": True},
                status=status.HTTP_202_ACCEPTED,
            )


class VenueMapVerifyView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        venue_map = InteractiveVenueMap.objects.get(pk=pk)
        venue_map.is_verified = True
        venue_map.verified_by = request.user
        venue_map.save(update_fields=["is_verified", "verified_by"])
        return Response({"status": "verified"})


class VenueMapZoneUpdateView(generics.UpdateAPIView):
    queryset = VenueMapZone.objects.all()
    serializer_class = VenueMapZoneSerializer
    permission_classes = [IsAdminRole]


class AgentTagZoneView(APIView):
    """Admin map agent: tag zone metadata via structured payload."""

    permission_classes = [IsAdminRole]

    def post(self, request):
        zone = VenueMapZone.objects.get(pk=request.data["zone_id"])
        zone.zone_label = request.data.get("zone_label", zone.zone_label)
        meta = zone.display_metadata_json or {}
        meta.update(request.data.get("metadata", {}))
        zone.display_metadata_json = meta
        if request.data.get("space_inventory_id"):
            zone.space_inventory_id = request.data["space_inventory_id"]
        zone.updated_by_agent = True
        zone.save()
        return Response(VenueMapZoneSerializer(zone).data)
