from rest_framework import serializers

from .models import SpaceInventory, VenueProperty


class VenuePropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = VenueProperty
        fields = ("id", "name", "timezone")


class SpaceInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceInventory
        fields = (
            "id",
            "property",
            "name",
            "space_type",
            "capacities_json",
            "base_floor_cost",
            "rack_rate",
            "av_capabilities_json",
        )
