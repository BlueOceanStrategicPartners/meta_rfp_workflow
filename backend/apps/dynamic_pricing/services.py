"""Dynamic pricing: one package, two demand engines (XGBoost or rule fallback), an exact explanation.

price steps (each an exact cent amount; running totals equal the stored prices):
  base → demand (model factors or seasonality) → [demand limit] → goal markup → [floor guard] = target
  target → opening-offer markup → [anchor guard] = anchor
floor = operating cost × (1 + floor margin)
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

from apps.core.exceptions import PricingBoundsViolationError
from apps.inventory.models import VenueProperty
from apps.rfp_debate.models import RFPSubmission

from . import model_store
from .explain import predict_with_contributions
from .features import feature_rows, history_for_dates, week_stats
from .models import DynamicPricingQuote, PricingPolicy
from .package import PackageBase, QuoteNotPossibleError, build_package, money
from .rule_fallback import RuleBasedPricingFallbackEngine
from .training import MIN_TRAINING_ROWS, data_counts, train_model

# The model predicts a demand index around 1.0; clamp it so one bad prediction cannot run away.
DEMAND_INDEX_MIN = 0.8
DEMAND_INDEX_MAX = 1.5
# Raw predictions outside this band are treated as broken (spec §9: PricingBoundsViolationError).
RAW_PREDICTION_BOUNDS = (0.5, 2.0)
MAX_STAY_NIGHTS = 30
MAX_DAYS_AHEAD = 730
FLOOR_GUARD = Decimal("1.05")  # target is at least 5% above the walk-away floor
ANCHOR_GUARD = Decimal("1.03")  # anchor is at least 3% above the target

FALLBACK_REASON_LABELS = {
    "": "",
    "no_model": "No trained model yet",
    "insufficient_history": "Not enough history to train",
    "model_not_better_than_baseline": "Model not better than a simple average",
    "prediction_out_of_bounds": "Model gave an unusual answer",
    "extreme_request": "Unusual request (very long or far ahead)",
    "model_error": "Model could not be used",
    "dates_missing": "Dates not confirmed yet",
}

__all__ = [
    "QuoteNotPossibleError",
    "compute_dynamic_quote",
    "client_quote_card",
    "autonomous_limit",
    "default_property",
    "model_status",
    "train_and_save_model",
    "FALLBACK_REASON_LABELS",
]


def default_property() -> VenueProperty:
    prop = VenueProperty.objects.order_by("created_at").first()
    return prop or VenueProperty.objects.create(name="Default Property")


class _Waterfall:
    """Collects price steps; every amount is rounded first so the running total is exact."""

    def __init__(self, base: Decimal):
        self.total = money(base)
        self.steps = [self._step("base", "Base price (rooms + meeting space)", "base", self.total)]

    def _step(self, key, label, kind, amount, ends=None):
        return {"key": key, "label": label, "kind": kind, "amount": str(amount), "running_total": str(self.total), "ends": ends}

    def add(self, key: str, label: str, kind: str, amount) -> None:
        amount = money(amount)
        if amount == 0:
            return
        self.total = money(self.total + amount)
        self.steps.append(self._step(key, label, kind, amount))

    def end(self, ends: str) -> None:
        self.steps[-1]["ends"] = ends


def _pct(value) -> str:
    pct = float(value) * 100
    return f"{pct:+.1f}%" if 0 < abs(pct) < 1 else f"{pct:+.0f}%"  # never show "-0%" next to a real amount


def _model_demand(prop: VenueProperty, pkg: PackageBase) -> tuple[dict | None, str, int | None]:
    """Returns (prediction, fallback_reason, model_version)."""
    if pkg.dates_assumed:
        return None, "dates_missing", None
    if pkg.nights > MAX_STAY_NIGHTS or (pkg.check_in - date.today()).days > MAX_DAYS_AHEAD:
        return None, "extreme_request", None
    try:
        active = model_store.active_model(prop.id)
    except Exception as exc:  # unreadable model file: keep pricing on the simple formula, show the error
        model_store.record_error(prop.id, f"{exc.__class__.__name__}: {exc}")
        meta = model_store.read_meta(prop.id) or {}
        return None, "model_error", meta.get("version")
    if active is None:
        meta = model_store.read_meta(prop.id)
        if meta and meta.get("inactive_reason"):
            return None, meta["inactive_reason"], None
        trainable = data_counts(prop)["trainable"]
        return None, ("insufficient_history" if trainable < MIN_TRAINING_ROWS else "no_model"), None
    booster, meta = active
    try:
        frame = history_for_dates(prop, pkg.stay_dates)
        stats = week_stats(frame, float(meta.get("mean_revpar") or 0) or 1.0)
        prediction = predict_with_contributions(booster, feature_rows(pkg.stay_dates, stats))
        raw = prediction["prediction"]
        if math.isnan(raw) or not RAW_PREDICTION_BOUNDS[0] <= raw <= RAW_PREDICTION_BOUNDS[1]:
            raise PricingBoundsViolationError(f"Demand prediction {raw:.3f} outside {RAW_PREDICTION_BOUNDS}")
    except PricingBoundsViolationError:
        return None, "prediction_out_of_bounds", meta.get("version")
    except Exception as exc:  # corrupt artifact, feature mismatch: report on the model card, keep pricing
        model_store.record_error(prop.id, f"{exc.__class__.__name__}: {exc}")
        return None, "model_error", meta.get("version")
    return prediction, "", meta.get("version")


def compute_dynamic_quote(rfp: RFPSubmission) -> DynamicPricingQuote:
    """Price the RFP's current cards. Raises QuoteNotPossibleError when it cannot be priced honestly."""
    prop = default_property()
    policy = PricingPolicy.get_solo()
    pkg = build_package(rfp.active_ui_cards_json or {}, prop, policy)
    base = pkg.base_price
    waterfall = _Waterfall(base)

    prediction, reason, version = _model_demand(prop, pkg)
    if prediction is not None:
        engine = "model"
        bias, raw = prediction["bias"], prediction["prediction"]
        waterfall.add("demand_normal", "Normal demand for these dates", "demand", base * Decimal(str(bias - 1)))
        for label, value in sorted(prediction["contributions"].items(), key=lambda kv: -abs(kv[1])):
            waterfall.add(f"demand:{label}", f"{label} ({_pct(value)})", "demand", base * Decimal(str(value)))
        demand = min(max(raw, DEMAND_INDEX_MIN), DEMAND_INDEX_MAX)
        if demand != raw:
            waterfall.add("demand_limit", f"Demand limit ({DEMAND_INDEX_MIN}–{DEMAND_INDEX_MAX}×)", "clamp", base * Decimal(str(demand - raw)))
        # Snap the running total to base × demand so rounding of many small factors cannot drift.
        waterfall.add("demand_rounding", "Rounding", "demand", money(base * Decimal(str(demand))) - waterfall.total)
    else:
        engine = "fallback"
        month = (pkg.check_in or date.today()).month
        demand = RuleBasedPricingFallbackEngine.multiplier(policy, month)
        waterfall.add("season", f"Season and event multiplier ({_pct(demand - 1)}, simple formula)", "demand", base * Decimal(str(demand - 1)))

    waterfall.add("goal_markup", f"Goal markup ({_pct(policy.target_markup_pct)})", "markup", waterfall.total * Decimal(str(policy.target_markup_pct)))
    floor = money(pkg.operating_cost * (Decimal("1") + Decimal(str(policy.walk_away_floor_margin_pct))))
    min_target = money(floor * FLOOR_GUARD)
    if waterfall.total < min_target:
        waterfall.add("floor_guard", "Raised to stay above the walk-away price", "guard", min_target - waterfall.total)
    waterfall.end("target")
    target = waterfall.total

    waterfall.add("anchor_markup", f"Opening-offer markup ({_pct(policy.anchor_markup_pct)})", "markup", target * Decimal(str(policy.anchor_markup_pct)))
    min_anchor = money(target * ANCHOR_GUARD)
    if waterfall.total < min_anchor:
        waterfall.add("anchor_guard", "Raised to leave room to negotiate", "guard", min_anchor - waterfall.total)
    waterfall.end("anchor")
    anchor = waterfall.total

    floor_steps = [
        {"key": "operating_cost", "label": "Operating cost (rooms + space)", "amount": str(pkg.operating_cost), "running_total": str(pkg.operating_cost)},
        {"key": "floor_margin", "label": f"Minimum margin ({_pct(policy.walk_away_floor_margin_pct)})", "amount": str(floor - pkg.operating_cost), "running_total": str(floor)},
    ]
    explanation = {"steps": waterfall.steps, "floor_steps": floor_steps}
    return DynamicPricingQuote.objects.create(
        rfp=rfp,
        xgboost_demand_score=float(demand),
        walk_away_floor_price=floor,
        optimal_target_price=target,
        initial_anchor_price=anchor,
        shap_explanations_json=explanation,
        explanation_json=explanation,
        inputs_json=pkg.as_inputs(),
        used_fallback_engine=engine == "fallback",
        engine=engine,
        model_version=version,
        fallback_reason=reason,
    )


def client_quote_card(quote: DynamicPricingQuote) -> dict:
    """What the client may see: the opening offer and a friendly breakdown. Never floor or target."""
    inputs = quote.inputs_json or {}
    return {
        "anchor_price": float(quote.initial_anchor_price),
        "estimate": bool(inputs.get("dates_assumed")),
        "breakdown": {
            "rooms": inputs.get("rooms_part"),
            "room_nights": inputs.get("room_nights"),
            "space": inputs.get("space_part"),
            "space_name": inputs.get("space_name"),
            "nights": inputs.get("nights"),
        },
    }


def autonomous_limit(quote: DynamicPricingQuote, policy: PricingPolicy | None = None) -> Decimal:
    """Lowest price the agent may agree on its own (spec §6.2 max autonomous discount).

    Below this (but above the floor) a person must approve; below the floor is always refused.
    """
    policy = policy or PricingPolicy.get_solo()
    discounted = money(quote.initial_anchor_price * (Decimal("1") - Decimal(str(policy.max_autonomous_discount_pct))))
    return max(quote.walk_away_floor_price, discounted)


def train_and_save_model(property_id) -> str:
    """Backward-compatible wrapper: returns the model path, or the skip status."""
    prop = VenueProperty.objects.get(pk=property_id)
    result = train_model(prop)
    if result["status"] == "skipped_insufficient_data":
        return "skipped_insufficient_data"
    return str(model_store.model_path(prop.id))


def model_status(prop: VenueProperty | None = None) -> dict:
    prop = prop or default_property()
    meta = model_store.read_meta(prop.id) or {}
    counts = data_counts(prop)
    return {
        "artifact_exists": model_store.model_path(prop.id).exists(),
        "trained_at": meta.get("trained_at"),
        "occupancy_rows": counts["trainable"],
        "min_rows_required": MIN_TRAINING_ROWS,
        "version": meta.get("version"),
        "is_active": bool(meta.get("is_active")),
        "inactive_reason": meta.get("inactive_reason") or "",
        "rows_used": meta.get("rows_used"),
        "date_from": meta.get("date_from"),
        "date_to": meta.get("date_to"),
        "metrics": meta.get("metrics"),
        "feature_importance": meta.get("feature_importance") or [],
        "data": counts,
        "last_error": meta.get("last_error") or "",
    }
