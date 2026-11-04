"""Exact per-factor explanation of the model's demand prediction.

XGBoost's own TreeSHAP (`pred_contribs=True`) gives additive contributions in the demand index:
prediction = bias + sum(contributions). Averaging over the stay nights keeps that identity, so
the waterfall built from these numbers adds up to the final price.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import FEATURE_LABELS, FEATURES


def predict_with_contributions(booster, features: pd.DataFrame) -> dict:
    import xgboost as xgb

    matrix = xgb.DMatrix(features[FEATURES], feature_names=FEATURES)
    contribs = booster.predict(matrix, pred_contribs=True)  # shape (nights, features + 1); last column = bias
    mean = np.asarray(contribs).mean(axis=0)
    grouped: dict[str, float] = {}
    for name, value in zip(FEATURES, mean[:-1]):
        label = FEATURE_LABELS[name]
        grouped[label] = grouped.get(label, 0.0) + float(value)
    bias = float(mean[-1])
    return {
        "bias": bias,
        "contributions": grouped,  # plain-language factor -> share of the demand index
        "prediction": bias + sum(grouped.values()),
    }
