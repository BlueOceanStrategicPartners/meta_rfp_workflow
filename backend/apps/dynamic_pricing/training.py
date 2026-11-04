"""Train the nightly demand model from real occupancy history (spec §8, plan D2).

Label: that day's RevPAR divided by the property's average RevPAR (a demand index, 1.0 = normal).
Validation uses the most recent 20% of days (time-based, never random), and the model is only
activated when it beats the simple same-week-average baseline.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from apps.inventory.models import HistoricalOccupancy, OccupancySource, VenueProperty

from . import model_store
from .features import FEATURE_LABELS, FEATURES, feature_rows, history_frame, trainable_rows, week_stats

MIN_TRAINING_ROWS = 60
VALIDATION_SHARE = 0.2


def data_counts(prop: VenueProperty) -> dict[str, int]:
    counts = {source.value: 0 for source in OccupancySource}
    for source in counts:
        counts[source] = HistoricalOccupancy.objects.filter(property=prop, source=source).count()
    counts["trainable"] = trainable_rows(prop).count()
    return counts


def _importance(model) -> list[dict]:
    gains = model.get_booster().get_score(importance_type="gain")
    grouped: dict[str, float] = {}
    for feature, gain in gains.items():
        label = FEATURE_LABELS.get(feature, feature)
        grouped[label] = grouped.get(label, 0.0) + gain
    total = sum(grouped.values()) or 1.0
    ranked = sorted(grouped.items(), key=lambda kv: kv[1], reverse=True)
    return [{"feature": label, "label": label, "importance": round(gain / total, 4)} for label, gain in ranked]


def train_model(prop: VenueProperty) -> dict:
    import xgboost as xgb

    frame = history_frame(trainable_rows(prop).order_by("target_date"))
    rows_available = len(frame)
    if rows_available < MIN_TRAINING_ROWS:
        return {
            "status": "skipped_insufficient_data",
            "detail": f"Need at least {MIN_TRAINING_ROWS} days of real history; found {rows_available}.",
            "rows_available": rows_available,
            "rows_required": MIN_TRAINING_ROWS,
        }

    frame = frame.sort_values("date").reset_index(drop=True)
    mean_revpar = float(frame["revpar"].mean()) or 1.0
    labels = (frame["revpar"] / mean_revpar).to_numpy()
    stats = week_stats(frame, mean_revpar)
    features = feature_rows(list(frame["date"]), stats)

    split = int(len(frame) * (1 - VALIDATION_SHARE))
    x_train, x_val = features.iloc[:split], features.iloc[split:]
    y_train, y_val = labels[:split], labels[split:]

    model = xgb.XGBRegressor(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="mae",
        early_stopping_rounds=30,
    )
    model.fit(x_train, y_train, eval_set=[(x_val, y_val)], verbose=False)
    predictions = model.predict(x_val)

    mae = float(np.mean(np.abs(predictions - y_val)))
    mape = float(np.mean(np.abs(predictions - y_val) / np.maximum(np.abs(y_val), 1e-6))) * 100
    baseline = x_val["hist_demand"].fillna(1.0).to_numpy()  # "simple average": same week in past years
    baseline_mae = float(np.mean(np.abs(baseline - y_val)))
    improvement = (baseline_mae - mae) / baseline_mae * 100 if baseline_mae else 0.0
    is_active = improvement > 0

    previous = model_store.read_meta(prop.id) or {}
    version = int(previous.get("version") or 0) + 1
    model_store.property_dir(prop.id).mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(str(model_store.model_path(prop.id)))
    meta = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "property_id": str(prop.id),
        "rows_used": rows_available,
        "date_from": frame["date"].iloc[0].isoformat(),
        "date_to": frame["date"].iloc[-1].isoformat(),
        "mean_revpar": mean_revpar,
        "features": FEATURES,
        "metrics": {
            "mae": round(mae, 4),
            "mape": round(mape, 2),
            "baseline_mae": round(baseline_mae, 4),
            "improvement_pct": round(improvement, 1),
        },
        "feature_importance": _importance(model),
        "is_active": is_active,
        "inactive_reason": "" if is_active else "model_not_better_than_baseline",
        "last_error": "",
    }
    model_store.write_meta(prop.id, meta)
    return {
        "status": "ok" if is_active else "inactive_not_better",
        "detail": "" if is_active else "The model was not better than a simple average, so quotes keep using the simple formula.",
        "trained_at": meta["trained_at"],
        "version": version,
        "metrics": meta["metrics"],
        "rows_available": rows_available,
        "rows_required": MIN_TRAINING_ROWS,
    }
