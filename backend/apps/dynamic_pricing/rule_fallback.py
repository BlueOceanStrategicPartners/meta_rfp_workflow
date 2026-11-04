from __future__ import annotations

from .models import PricingPolicy


class RuleBasedPricingFallbackEngine:
    """Spec §9 fallback: rack-rate package × seasonality × event multiplier (bounded by the floor later).

    It prices the same PackageBase as the XGBoost path; only the demand multiplier differs.
    """

    @staticmethod
    def multiplier(policy: PricingPolicy, month: int | None) -> float:
        return policy.season(month) * float(policy.event_multiplier)
