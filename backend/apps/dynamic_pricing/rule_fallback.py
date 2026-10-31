from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from apps.inventory.models import SpaceInventory, VenueProperty


class RuleBasedPricingFallbackEngine:
    @staticmethod
    def quote(property: VenueProperty, features: dict) -> tuple[float, dict[str, Decimal]]:
        space = (
            SpaceInventory.objects.filter(property=property).order_by("-rack_rate").first()
        )
        rack = Decimal(str(space.rack_rate if space else 250))
        seasonality = Decimal("1.15") if features.get("month") in (6, 7, 11, 12) else Decimal("1.0")
        duration = Decimal(str(features.get("event_duration_days", 1)))
        base = rack * duration * seasonality
        margin = Decimal(str(settings.WALK_AWAY_FLOOR_MARGIN_PCT))
        floor = base * (Decimal("1") + margin)
        if space and floor < space.base_floor_cost:
            floor = space.base_floor_cost
        target = base * Decimal("1.1")
        anchor = target * Decimal("1.08")
        demand_score = float(features.get("avg_historical_occupancy", 0.7))
        return demand_score, {"floor": floor, "target": target, "anchor": anchor}
