"""Multi-turn voice intake — gate pipeline + session side effects.

Architecture (industry pattern):
  1. Fast path: deterministic gates (slots, state machine, inventory) — no LLM.
  2. Session memory + cards are authoritative context (not re-parsed keywords alone).
  3. Optional LLM tier (voice_intake_llm) only when gates return NO_MATCH and API available.

Legacy helpers (record_availability_window) stay here for planning/availability modules.
"""
from __future__ import annotations

from typing import Any

from apps.rfp_debate.models import RFPSubmission

from .client_group_context import ensure_group_size_on_cards
from .client_session_memory import normalize_session, record_assistant_reply
from .voice_intake_gates import IntakeGateResult, availability_window, run_intake_gate_pipeline


def _intake_block(session: dict) -> dict:
    raw = session.get("intake")
    return raw if isinstance(raw, dict) else {}


def record_availability_window(rfp: RFPSubmission, table: dict[str, Any] | None) -> None:
    if not table:
        return
    start_iso = (table.get("window_start_iso") or "").strip()
    if not start_iso:
        rows = table.get("rows") or []
        if rows and rows[0].get("date_iso"):
            start_iso = str(rows[0]["date_iso"])[:10]
    if not start_iso:
        return
    session = normalize_session(rfp.client_session_json)
    intake = _intake_block(session)
    intake["availability_window_start"] = start_iso[:10]
    intake["availability_window_days"] = int(table.get("window_days") or 7)
    session["intake"] = intake
    rfp.client_session_json = session


def try_voice_intake_followup(
    rfp: RFPSubmission | None,
    message: str,
) -> str | None:
    """Run intake gate pipeline; return spoken reply or None."""
    if not rfp:
        return None
    cleaned = (message or "").strip()
    if not cleaned:
        return None

    ensure_group_size_on_cards(rfp)
    outcome = run_intake_gate_pipeline(rfp, cleaned)
    if outcome is None:
        return None
    if isinstance(outcome, str):
        return outcome
    if isinstance(outcome, IntakeGateResult):
        return outcome.spoken
    return None


def persist_intake_reply(rfp: RFPSubmission, reply: str) -> None:
    record_assistant_reply(rfp, reply)
