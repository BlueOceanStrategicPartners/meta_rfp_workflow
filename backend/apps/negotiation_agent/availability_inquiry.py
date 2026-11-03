"""Availability Q&A — DB lookup + generative table payload for client voice/chat."""
from __future__ import annotations

from typing import Any

from apps.inventory.room_availability import (
    build_availability_table,
    detect_availability_inquiry,
    spoken_availability_for_message,
    spoken_availability_intro,
)


def try_availability_response(message: str) -> tuple[str, dict[str, Any] | None] | None:
    """
    When the user asks about suitable dates / next-week visits, return spoken line + UI table.
    Returns None if this turn is not an availability inquiry.
    """
    if not detect_availability_inquiry(message):
        return None
    table = build_availability_table()
    if not table.get("rows"):
        return (
            "I don't have property inventory loaded yet — share your target arrival day and I'll verify it.",
            None,
        )
    spoken = spoken_availability_for_message(table, message)
    return spoken, table
