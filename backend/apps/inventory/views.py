from rest_framework import generics

from apps.accounts_rbac.permissions import IsAdminRole

from .models import SpaceInventory, VenueProperty
from .serializers import SpaceInventorySerializer, VenuePropertySerializer


class PropertyListView(generics.ListAPIView):
    queryset = VenueProperty.objects.all()
    serializer_class = VenuePropertySerializer
    permission_classes = []


class SpaceListView(generics.ListAPIView):
    queryset = SpaceInventory.objects.select_related("property")
    serializer_class = SpaceInventorySerializer
    permission_classes = [IsAdminRole]
