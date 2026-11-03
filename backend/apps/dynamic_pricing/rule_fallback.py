from __future__ import annotations

from decimal import Decimal

from apps.inventory.models import SpaceInventory, VenueProperty

from .models import PricingPolicy


def enforce_ladder(floor: Decimal, target: Decimal, anchor: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Keep floor < target < anchor so the agent's goal never sits below its walk-away price."""
    target = max(target, floor * Decimal("1.05"))
    anchor = max(anchor, target * Decimal("1.03"))
    return floor, target, anchor


class RuleBasedPricingFallbackEngine:
    @staticmethod
    def quote(
        property: VenueProperty, features: dict, policy: PricingPolicy | None = None
    ) -> tuple[float, dict[str, Decimal]]:
        policy = policy or PricingPolicy.get_solo()
        space = (
            SpaceInventory.objects.filter(property=property).order_by("-rack_rate").first()
        )
        rack = Decimal(str(space.rack_rate if space else 250))
        seasonality = Decimal(str(policy.season(features.get("month"))))
        event_multiplier = Decimal(str(policy.event_multiplier))
        duration = Decimal(str(features.get("event_duration_days", 1)))
        base = rack * duration * seasonality * event_multiplier
        floor = base * (Decimal("1") + Decimal(str(policy.walk_away_floor_margin_pct)))
        if space and floor < space.base_floor_cost:
            floor = space.base_floor_cost
        target = base * (Decimal("1") + Decimal(str(policy.target_markup_pct)))
        anchor = target * (Decimal("1") + Decimal(str(policy.anchor_markup_pct)))
        floor, target, anchor = enforce_ladder(floor, target, anchor)
        demand_score = float(features.get("avg_historical_occupancy", 0.7))
        return demand_score, {"floor": floor, "target": target, "anchor": anchor}
