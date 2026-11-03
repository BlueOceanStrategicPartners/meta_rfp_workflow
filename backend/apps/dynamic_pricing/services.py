from __future__ import annotations

import json
import math
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import models

from apps.core.exceptions import PricingBoundsViolationError
from apps.inventory.models import HistoricalOccupancy, SpaceInventory, VenueProperty
from apps.rfp_debate.models import RFPSubmission

from .models import DynamicPricingQuote, PricingPolicy
from .rule_fallback import RuleBasedPricingFallbackEngine, enforce_ladder

MODEL_PATH = Path(settings.BASE_DIR) / "artifacts" / "xgboost_pricing.json"
MODEL_META_PATH = MODEL_PATH.with_suffix(".meta.json")
MIN_TRAINING_ROWS = 5
# The model predicts a demand index around 1.0; clamp it so one bad prediction cannot run away.
DEMAND_INDEX_MIN = 0.8
DEMAND_INDEX_MAX = 1.5
FEATURE_COLUMNS = [
    "days_until_event",
    "event_duration_days",
    "avg_historical_occupancy",
    "avg_adr",
    "requested_rooms_ratio",
    "meeting_headcount",
    "month",
]


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def build_feature_vector(rfp: RFPSubmission, property_id) -> dict:
    cards = rfp.active_ui_cards_json or {}
    overview = cards.get("event_overview", {})
    meeting = cards.get("meeting_space", {})
    room_block = cards.get("room_block", {})
    check_in = _parse_date(overview.get("check_in_date"))
    days_until = (check_in - date.today()).days if check_in else 30
    duration = 1
    co = _parse_date(overview.get("check_out_date"))
    if check_in and co:
        duration = max((co - check_in).days, 1)
    hist_qs = HistoricalOccupancy.objects.filter(property_id=property_id)
    if check_in:
        hist_qs = hist_qs.filter(target_date__month=check_in.month)
    agg = hist_qs.aggregate(avg_occ=models.Avg("room_occupancy_pct"), avg_adr=models.Avg("adr"))
    avg_occ = float(agg["avg_occ"] or 0.65)
    avg_adr = float(agg["avg_adr"] or 200)
    total_rooms = sum(
        b.get("single", 0) + b.get("double", 0) + b.get("deluxe", 0) + b.get("suite", 0)
        for b in room_block.get("blocks", [])
    )
    spaces = SpaceInventory.objects.filter(property_id=property_id)
    total_available = spaces.filter(space_type="ROOM_BLOCK").count() or 100
    headcount = float(meeting.get("headcount") or 0)
    return {
        "days_until_event": days_until,
        "event_duration_days": duration,
        "avg_historical_occupancy": avg_occ,
        "avg_adr": avg_adr,
        "requested_rooms_ratio": total_rooms / max(total_available, 1),
        "meeting_headcount": headcount,
        "month": check_in.month if check_in else date.today().month,
    }


def _predict_with_xgboost(features: dict) -> tuple[float, dict]:
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise PricingBoundsViolationError("XGBoost not available") from exc

    if not MODEL_PATH.exists():
        raise PricingBoundsViolationError("Model artifact missing")

    try:
        import numpy as np

        booster = xgb.Booster()
        booster.load_model(str(MODEL_PATH))
        row = np.array([[float(features[name]) for name in FEATURE_COLUMNS]])
        dmatrix = xgb.DMatrix(row, feature_names=FEATURE_COLUMNS)
        score = float(booster.predict(dmatrix)[0])
    except Exception as exc:  # corrupt artifact / feature mismatch -> rule-based fallback
        raise PricingBoundsViolationError(f"Model prediction failed: {exc}") from exc
    if math.isnan(score) or score <= 0:
        raise PricingBoundsViolationError("Invalid model output")
    score = min(max(score, DEMAND_INDEX_MIN), DEMAND_INDEX_MAX)
    shap = {
        "top_features": [
            {"name": "avg_historical_occupancy", "impact": features["avg_historical_occupancy"]},
            {"name": "requested_rooms_ratio", "impact": features["requested_rooms_ratio"]},
        ]
    }
    return score, shap


def compute_dynamic_quote(rfp: RFPSubmission) -> DynamicPricingQuote:
    prop = VenueProperty.objects.first()
    if not prop:
        prop = VenueProperty.objects.create(name="Default Property")
    features = build_feature_vector(rfp, prop.id)
    policy = PricingPolicy.get_solo()
    used_fallback = False
    try:
        if HistoricalOccupancy.objects.filter(property=prop).count() == 0:
            raise PricingBoundsViolationError("No historical rows")
        demand_score, shap_json = _predict_with_xgboost(features)
    except PricingBoundsViolationError:
        used_fallback = True
        demand_score, prices = RuleBasedPricingFallbackEngine.quote(prop, features, policy)
        shap_json = {"fallback": True, "demand_score": demand_score}
        floor = prices["floor"]
        target = prices["target"]
        anchor = prices["anchor"]
    else:
        base = (
            Decimal(str(features["avg_adr"]))
            * Decimal(str(features["event_duration_days"]))
            * Decimal(str(policy.season(features.get("month"))))
            * Decimal(str(policy.event_multiplier))
        )
        multiplier = Decimal(str(demand_score))
        floor = base * (Decimal("1") + Decimal(str(policy.walk_away_floor_margin_pct)))
        target = base * multiplier * (Decimal("1") + Decimal(str(policy.target_markup_pct)))
        anchor = target * (Decimal("1") + Decimal(str(policy.anchor_markup_pct)))
        space_floor = (
            SpaceInventory.objects.filter(property=prop).order_by("base_floor_cost").first()
        )
        if space_floor and floor < space_floor.base_floor_cost:
            floor = space_floor.base_floor_cost
        floor, target, anchor = enforce_ladder(floor, target, anchor)

    quote = DynamicPricingQuote.objects.create(
        rfp=rfp,
        xgboost_demand_score=float(demand_score),
        walk_away_floor_price=floor,
        optimal_target_price=target,
        initial_anchor_price=anchor,
        shap_explanations_json=shap_json,
        used_fallback_engine=used_fallback,
    )
    return quote


def train_and_save_model(property_id) -> str:
    """Train a minimal XGBoost regressor from HistoricalOccupancy and persist artifact."""
    import pandas as pd
    import xgboost as xgb

    rows = HistoricalOccupancy.objects.filter(property_id=property_id)
    if rows.count() < MIN_TRAINING_ROWS:
        return "skipped_insufficient_data"
    mean_revpar = float(rows.aggregate(m=models.Avg("revpar"))["m"] or 0) or 1.0
    records = []
    for row in rows:
        records.append(
            {
                "days_until_event": 30,
                "event_duration_days": 3,
                "avg_historical_occupancy": row.room_occupancy_pct,
                "avg_adr": float(row.adr),
                "requested_rooms_ratio": 0.5,
                "meeting_headcount": 200,
                "month": row.target_date.month,
                # Demand index (~1.0): RevPAR relative to the property average, not raw currency.
                "label": float(row.revpar) / mean_revpar,
            }
        )
    df = pd.DataFrame(records)
    feature_cols = FEATURE_COLUMNS
    dtrain = xgb.DMatrix(df[feature_cols], label=df["label"])
    model = xgb.train({"objective": "reg:squarederror"}, dtrain, num_boost_round=10)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_PATH))
    MODEL_META_PATH.write_text(
        json.dumps({"trained_at": datetime.now().astimezone().isoformat(), "rows": len(records)}),
        encoding="utf-8",
    )
    return str(MODEL_PATH)


def model_status() -> dict:
    trained_at = None
    if MODEL_META_PATH.exists():
        try:
            trained_at = json.loads(MODEL_META_PATH.read_text(encoding="utf-8")).get("trained_at")
        except (OSError, ValueError):
            trained_at = None
    return {
        "artifact_exists": MODEL_PATH.exists(),
        "trained_at": trained_at,
        "occupancy_rows": HistoricalOccupancy.objects.count(),
        "min_rows_required": MIN_TRAINING_ROWS,
    }
