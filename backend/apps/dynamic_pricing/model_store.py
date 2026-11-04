"""Per-property model artifacts: artifacts/pricing/<property_id>/{model.json, meta.json}.

Loaded boosters are cached in memory and reloaded only when the file changes, so pricing a
request does not read the model from disk every time.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

ARTIFACT_ROOT = Path(settings.BASE_DIR) / "artifacts" / "pricing"

_booster_cache: dict[str, tuple[float, object]] = {}


def property_dir(property_id) -> Path:
    return ARTIFACT_ROOT / str(property_id)


def model_path(property_id) -> Path:
    return property_dir(property_id) / "model.json"


def meta_path(property_id) -> Path:
    return property_dir(property_id) / "meta.json"


def read_meta(property_id) -> dict | None:
    path = meta_path(property_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_meta(property_id, meta: dict) -> None:
    property_dir(property_id).mkdir(parents=True, exist_ok=True)
    meta_path(property_id).write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")


def record_error(property_id, message: str) -> None:
    meta = read_meta(property_id)
    if meta is not None:
        meta["last_error"] = message[:500]
        write_meta(property_id, meta)


def load_booster(property_id):
    """Cached xgboost.Booster for the property, or None when no model file exists."""
    import xgboost as xgb

    path = model_path(property_id)
    if not path.exists():
        return None
    key = str(property_id)
    mtime = path.stat().st_mtime
    cached = _booster_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    booster = xgb.Booster()
    booster.load_model(str(path))
    _booster_cache[key] = (mtime, booster)
    return booster


def active_model(property_id) -> tuple[object, dict] | None:
    """(booster, meta) when an active model is available for pricing, else None."""
    meta = read_meta(property_id)
    if not meta or not meta.get("is_active"):
        return None
    booster = load_booster(property_id)
    return (booster, meta) if booster is not None else None
