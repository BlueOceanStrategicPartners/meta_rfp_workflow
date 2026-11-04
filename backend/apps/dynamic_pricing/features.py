"""Nightly demand features for the XGBoost model (spec §8.1).

Each stay night is described by its calendar position plus what happened in the same ISO
week over the previous three years. Only trainable (non-generated), past rows are used, and a
row never sees its own year's week, so training has no leakage.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

import pandas as pd

from apps.inventory.models import TRAINABLE_OCCUPANCY_SOURCES, HistoricalOccupancy, VenueProperty

HISTORY_YEARS = 3

FEATURES = [
    "dow_sin",
    "dow_cos",
    "month_sin",
    "month_cos",
    "week_of_year",
    "hist_occ",
    "hist_adr",
    "hist_demand",
    "hist_peak_share",
    "hist_event_mult",
]

# Plain-language groups shown in explanations (several encodings collapse into one factor).
FEATURE_LABELS = {
    "dow_sin": "Day of the week",
    "dow_cos": "Day of the week",
    "month_sin": "Time of year",
    "month_cos": "Time of year",
    "week_of_year": "Time of year",
    "hist_occ": "Past occupancy that week",
    "hist_adr": "Past room prices that week",
    "hist_demand": "Past demand that week",
    "hist_peak_share": "Busy days that week in past years",
    "hist_event_mult": "Past city events that week",
}


def trainable_rows(prop: VenueProperty):
    return HistoricalOccupancy.objects.filter(
        property=prop, source__in=TRAINABLE_OCCUPANCY_SOURCES, target_date__lt=date.today()
    )


def history_frame(queryset) -> pd.DataFrame:
    rows = list(
        queryset.values_list(
            "target_date", "room_occupancy_pct", "adr", "revpar", "is_peak_season", "local_event_multiplier"
        )
    )
    frame = pd.DataFrame(rows, columns=["date", "occ", "adr", "revpar", "peak", "event"])
    if not frame.empty:
        frame["adr"] = frame["adr"].astype(float)
        frame["revpar"] = frame["revpar"].astype(float)
        frame["peak"] = frame["peak"].astype(float)
    return frame


def history_for_dates(prop: VenueProperty, dates: list[date]) -> pd.DataFrame:
    """One query: the same ISO weeks in the previous HISTORY_YEARS years (fast at quote time)."""
    if not dates:
        return history_frame(HistoricalOccupancy.objects.none())
    weeks = sorted({d.isocalendar()[1] for d in dates})
    first_year = min(d.isocalendar()[0] for d in dates) - HISTORY_YEARS
    return history_frame(
        trainable_rows(prop).filter(target_date__week__in=weeks, target_date__iso_year__gte=first_year)
    )


def week_stats(frame: pd.DataFrame, mean_revpar: float) -> dict[tuple[int, int], dict[str, float]]:
    stats: dict[tuple[int, int], dict[str, float]] = {}
    if frame.empty:
        return stats
    buckets: dict[tuple[int, int], list] = defaultdict(list)
    for row in frame.itertuples(index=False):
        iso = row.date.isocalendar()
        buckets[(iso[0], iso[1])].append(row)
    for key, rows in buckets.items():
        n = len(rows)
        stats[key] = {
            "hist_occ": sum(r.occ for r in rows) / n,
            "hist_adr": sum(r.adr for r in rows) / n,
            "hist_demand": (sum(r.revpar for r in rows) / n) / mean_revpar if mean_revpar else float("nan"),
            "hist_peak_share": sum(r.peak for r in rows) / n,
            "hist_event_mult": sum(r.event for r in rows) / n,
        }
    return stats


def feature_rows(dates: list[date], stats: dict[tuple[int, int], dict[str, float]]) -> pd.DataFrame:
    records = []
    for d in dates:
        iso_year, iso_week, _ = d.isocalendar()
        prior = [stats[(iso_year - k, iso_week)] for k in range(1, HISTORY_YEARS + 1) if (iso_year - k, iso_week) in stats]
        record = {
            "dow_sin": math.sin(2 * math.pi * d.weekday() / 7),
            "dow_cos": math.cos(2 * math.pi * d.weekday() / 7),
            "month_sin": math.sin(2 * math.pi * (d.month - 1) / 12),
            "month_cos": math.cos(2 * math.pi * (d.month - 1) / 12),
            "week_of_year": float(iso_week),
        }
        for name in ("hist_occ", "hist_adr", "hist_demand", "hist_peak_share", "hist_event_mult"):
            values = [p[name] for p in prior if not math.isnan(p[name])]
            record[name] = sum(values) / len(values) if values else float("nan")  # XGBoost handles NaN
        records.append(record)
    return pd.DataFrame(records, columns=FEATURES)
