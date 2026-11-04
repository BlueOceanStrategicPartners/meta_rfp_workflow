"""Detect room-only stays (no meeting space) and keep cards + proposal in sync."""
from __future__ import annotations

import re

from apps.rfp_debate.models import RFPSubmission

from .client_session_memory import normalize_session

_DECLINE_PATTERNS = (
    r"\bno\s+meeting\s+space\b",
    r"\bwithout\s+meeting\s+space\b",
    r"\bdon'?t\s+(?:want|need)\s+(?:the\s+)?meeting\b",
    r"\bdo\s+not\s+(?:want|need)\s+(?:the\s+)?meeting\b",
    r"\bnot\s+(?:want|need)\s+(?:the\s+)?meeting\b",
    r"\bno\s+meeting\b",
    r"\brooms?\s+only\b",
    r"\broom\s+block\s+only\b",
    r"\bno\s+(?:function|event)\s+space\b",
    # Common speech-to-text mis-hearings
    r"\bmeat\s+in\s+space\b",
    r"\bmeeting\s+in\s+space\b",
)

_REQUEST_PATTERNS = (
    r"\bneed\s+meeting\s+space\b",
    r"\bwant\s+meeting\s+space\b",
    r"\badd\s+meeting\s+space\b",
    r"\bwith\s+meeting\s+space\b",
)


def message_declines_meeting_space(message: str) -> bool:
    lower = (message or "").lower()
    if not lower.strip():
        return False
    if message_requests_meeting_space(message):
        return False
    return any(re.search(p, lower) for p in _DECLINE_PATTERNS)


def message_requests_meeting_space(message: str) -> bool:
    lower = (message or "").lower()
    return any(re.search(p, lower) for p in _REQUEST_PATTERNS)


def meeting_space_wanted_for_cards(cards: dict, session: dict) -> bool:
    intake = session.get("intake") or {}
    if isinstance(intake, dict):
        flag = str(intake.get("needs_meeting_space") or "").strip().lower()
        if flag in ("0", "false", "no", "off"):
            return False
    meeting = cards.get("meeting_space") or {}
    if meeting.get("included") is False:
        return False
    return True


def meeting_space_wanted(rfp: RFPSubmission | None) -> bool:
    if not rfp:
        return True
    session = normalize_session(rfp.client_session_json)
    intake = session.get("intake") or {}
    if isinstance(intake, dict):
        flag = str(intake.get("needs_meeting_space") or "").strip().lower()
        if flag in ("0", "false", "no", "off"):
            return False
    cards = rfp.active_ui_cards_json or {}
    meeting = cards.get("meeting_space") or {}
    if meeting.get("included") is False:
        return False
    return True


def meeting_space_exclusion_patch() -> dict:
    return {
        "meeting_space": {
            "headcount": None,
            "seating_style": None,
            "av": None,
            "included": False,
        },
        "catering_av": {"catering": None, "av": None},
    }


def persist_meeting_space_preference(rfp: RFPSubmission, *, wanted: bool) -> None:
    session = normalize_session(rfp.client_session_json)
    intake = dict(session.get("intake") or {})
    intake["needs_meeting_space"] = "1" if wanted else "0"
    session["intake"] = intake
    rfp.client_session_json = session


def try_apply_meeting_space_decline(rfp: RFPSubmission, message: str) -> bool:
    if not message_declines_meeting_space(message):
        return False
    persist_meeting_space_preference(rfp, wanted=False)
    rfp.save(update_fields=["client_session_json", "updated_at"])
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(str(rfp.id), meeting_space_exclusion_patch())
    rfp.refresh_from_db()
    return True


def try_apply_meeting_space_request(rfp: RFPSubmission, message: str) -> bool:
    if not message_requests_meeting_space(message):
        return False
    persist_meeting_space_preference(rfp, wanted=True)
    rfp.save(update_fields=["client_session_json", "updated_at"])
    patch = {"meeting_space": {"included": True}}
    from apps.ui_card_validator.services import validate_card_mutation

    validate_card_mutation(str(rfp.id), patch)
    rfp.refresh_from_db()
    return True
