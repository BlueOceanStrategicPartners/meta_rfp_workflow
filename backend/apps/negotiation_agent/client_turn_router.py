"""Route client voice turns — social chat vs planning vs full extraction/debate."""
from __future__ import annotations

import re

from .client_inquiry import detect_planning_turn


def is_social_greeting(message: str) -> bool:
    """Small talk without RFP facts — skip debate, cards, and long LLM loops."""
    cleaned = (message or "").strip()
    if not cleaned or len(cleaned) > 140:
        return False
    lower = cleaned.lower()
    if detect_planning_turn(cleaned):
        return False
    if re.search(
        r"\b(\d+\s*(participants?|guests|rooms?|nights?)|next week|check[\s-]?in|room block)\b",
        lower,
    ):
        return False
    if re.search(r"^(start|run|begin|analyze|process)\b", lower):
        return False
    if re.match(r"^(hi|hello|hey|good\s+(morning|afternoon|evening))[\s,!.?]*", lower):
        return True
    if "how are you" in lower and ("?" in cleaned or len(cleaned) < 90):
        if not re.search(r"\b(book|rfp|room block|participants?)\b", lower):
            return True
    if re.match(r"^(thanks?|thank you)[\s,!.?]*", lower) and len(cleaned) < 80:
        return True
    return False


def needs_debate_extraction(message: str) -> bool:
    """Only run the 3-agent debate when the user supplied extractable RFP content."""
    cleaned = (message or "").strip()
    if not cleaned or is_social_greeting(cleaned):
        return False
    if detect_planning_turn(cleaned):
        return False
    lower = cleaned.lower()
    if re.search(r"^(start|run|begin|analyze|process)\b", lower):
        return True
    if len(cleaned) >= 200 and re.search(r"\b(rfp|proposal|catering|breakout|room block)\b", lower):
        return True
    if re.search(r"\battach|upload|pdf\b", lower):
        return True
    return False
