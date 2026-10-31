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

from .models import DynamicPricingQuote
from .rule_fallback import RuleBasedPricingFallbackEngine

MODEL_PATH = Path(settings.BASE_DIR) / "artifacts" / "xgboost_pricing.json"


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

    booster = xgb.Booster()
    booster.load_model(str(MODEL_PATH))
    row = [[
        features["days_until_event"],
        features["event_duration_days"],
        features["avg_historical_occupancy"],
        features["avg_adr"],
        features["requested_rooms_ratio"],
        features["meeting_headcount"],
        features["month"],
    ]]
    import xgboost as xgb

    dmatrix = xgb.DMatrix(row)
    score = float(booster.predict(dmatrix)[0])
    if math.isnan(score) or score <= 0:
        raise PricingBoundsViolationError("Invalid model output")
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
    used_fallback = False
    try:
        if HistoricalOccupancy.objects.filter(property=prop).count() == 0:
            raise PricingBoundsViolationError("No historical rows")
        demand_score, shap_json = _predict_with_xgboost(features)
    except PricingBoundsViolationError:
        used_fallback = True
        demand_score, prices = RuleBasedPricingFallbackEngine.quote(prop, features)
        shap_json = {"fallback": True, "demand_score": demand_score}
        floor = prices["floor"]
        target = prices["target"]
        anchor = prices["anchor"]
    else:
        base = Decimal(str(features["avg_adr"])) * Decimal(str(features["event_duration_days"]))
        multiplier = Decimal(str(max(demand_score, 0.5)))
        margin = Decimal(str(settings.WALK_AWAY_FLOOR_MARGIN_PCT))
        floor = base * (Decimal("1") + margin)
        target = base * multiplier * Decimal("1.08")
        anchor = target * Decimal("1.12")
        space_floor = (
            SpaceInventory.objects.filter(property=prop).order_by("base_floor_cost").first()
        )
        if space_floor and floor < space_floor.base_floor_cost:
            floor = space_floor.base_floor_cost

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
    if rows.count() < 5:
        return "skipped_insufficient_data"
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
                "label": float(row.revpar),
            }
        )
    df = pd.DataFrame(records)
    feature_cols = [
        "days_until_event",
        "event_duration_days",
        "avg_historical_occupancy",
        "avg_adr",
        "requested_rooms_ratio",
        "meeting_headcount",
        "month",
    ]
    dtrain = xgb.DMatrix(df[feature_cols], label=df["label"])
    model = xgb.train({"objective": "reg:squarederror"}, dtrain, num_boost_round=10)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_PATH))
    return str(MODEL_PATH)
