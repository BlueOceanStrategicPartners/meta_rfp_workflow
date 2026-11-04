"""Muse model selection for the client RFP voice/text assistant (latency-optimized Spark)."""
from __future__ import annotations

from django.conf import settings


def client_assistant_model_id() -> str:
    """Fast Muse tier for client intake — Spark, not Wonder."""
    explicit = getattr(settings, "META_MODEL_CLIENT_ASSISTANT", "") or ""
    if explicit.strip():
        return explicit.strip()
    return settings.META_MODEL_SPARK


def client_assistant_reasoning_effort() -> str | None:
    raw = str(getattr(settings, "META_MODEL_CLIENT_ASSISTANT_REASONING_EFFORT", "low") or "").strip()
    if not raw or raw.lower() in {"none", "off", "false", "0"}:
        return None
    return raw.lower()
