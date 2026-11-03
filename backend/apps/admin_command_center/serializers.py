from __future__ import annotations

from rest_framework import serializers

from apps.dynamic_pricing.models import PricingPolicy
from apps.inventory.models import HistoricalOccupancy, SpaceInventory, VenueProperty

SEATING_STYLES = ("banquet", "classroom", "theater", "u_shape", "cocktail")


class AdminPropertySerializer(serializers.ModelSerializer):
    space_count = serializers.SerializerMethodField()

    class Meta:
        model = VenueProperty
        fields = ("id", "name", "timezone", "space_count")
        read_only_fields = ("id", "space_count")

    def get_space_count(self, obj) -> int:
        return obj.spaces.count()


class AdminSpaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceInventory
        fields = (
            "id",
            "property",
            "name",
            "space_type",
            "capacities_json",
            "rack_rate",
            "base_floor_cost",
            "av_capabilities_json",
            "is_booked",
        )
        read_only_fields = ("id", "is_booked")

    def validate_capacities_json(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Capacities must be an object of seating style to number of people.")
        cleaned = {}
        for key, raw in value.items():
            if key not in SEATING_STYLES:
                raise serializers.ValidationError(f"Unknown seating style '{key}'.")
            if raw in (None, ""):
                continue
            try:
                number = int(raw)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"Capacity for {key} must be a whole number.")
            if number < 0:
                raise serializers.ValidationError(f"Capacity for {key} cannot be negative.")
            cleaned[key] = number
        return cleaned

    def validate(self, attrs):
        rack = attrs.get("rack_rate", getattr(self.instance, "rack_rate", None))
        floor = attrs.get("base_floor_cost", getattr(self.instance, "base_floor_cost", None))
        if rack is not None and floor is not None:
            if rack < 0 or floor < 0:
                raise serializers.ValidationError("Prices cannot be negative.")
            if floor > rack:
                raise serializers.ValidationError(
                    {"base_floor_cost": "Floor cost cannot be higher than the rack rate."}
                )
        return attrs


class AdminOccupancySerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalOccupancy
        fields = (
            "id",
            "property",
            "target_date",
            "room_occupancy_pct",
            "hall_utilization_pct",
            "adr",
            "revpar",
            "is_peak_season",
            "local_event_multiplier",
        )


class PricingPolicySerializer(serializers.ModelSerializer):
    updated_by = serializers.SerializerMethodField()

    class Meta:
        model = PricingPolicy
        fields = (
            "walk_away_floor_margin_pct",
            "max_autonomous_discount_pct",
            "target_markup_pct",
            "anchor_markup_pct",
            "event_multiplier",
            "seasonality_json",
            "updated_by",
            "updated_at",
        )
        read_only_fields = ("updated_by", "updated_at")

    def get_updated_by(self, obj):
        return obj.updated_by.email if obj.updated_by_id else None

    def validate_walk_away_floor_margin_pct(self, value):
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Floor margin must be between 0% and 100%.")
        return value

    def validate_max_autonomous_discount_pct(self, value):
        if not 0 <= value <= 0.5:
            raise serializers.ValidationError("Maximum discount must be between 0% and 50%.")
        return value

    def validate_anchor_markup_pct(self, value):
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Anchor markup must be between 0% and 100%.")
        return value

    def validate_event_multiplier(self, value):
        if not 0.5 <= value <= 3:
            raise serializers.ValidationError("Event multiplier must be between 0.5 and 3.")
        return value

    def validate_seasonality_json(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Seasonality must map month numbers to multipliers.")
        cleaned = {}
        for key, raw in value.items():
            if str(key) not in {str(m) for m in range(1, 13)}:
                raise serializers.ValidationError(f"'{key}' is not a month number (1-12).")
            try:
                number = float(raw)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"Month {key} needs a number.")
            if not 0.5 <= number <= 3:
                raise serializers.ValidationError(f"Month {key} multiplier must be between 0.5 and 3.")
            cleaned[str(key)] = number
        return cleaned

    def validate(self, attrs):
        margin = attrs.get(
            "walk_away_floor_margin_pct", getattr(self.instance, "walk_away_floor_margin_pct", 0)
        )
        target = attrs.get("target_markup_pct", getattr(self.instance, "target_markup_pct", 0))
        if target <= margin:
            raise serializers.ValidationError(
                {"target_markup_pct": "Target markup must be higher than the floor margin, or the goal price would sit below the walk-away price."}
            )
        return attrs
