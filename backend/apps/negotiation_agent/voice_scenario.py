"""Spoken lines for the client voice assistant — end-user hospitality tone only."""
from __future__ import annotations

import re

from apps.rfp_debate.models import RFPSubmission

# Internal card placeholders — never read aloud as a company name.
_PLACEHOLDER_ORGANIZATIONS = frozenset(
    {"voice rfp session", "your organization", "your organisation"},
)


def _is_placeholder_org(name: str | None) -> bool:
    if not name or not str(name).strip():
        return True
    return str(name).strip().lower() in _PLACEHOLDER_ORGANIZATIONS


def rfp_has_meaningful_cards(rfp: RFPSubmission | None) -> bool:
    """True when cards hold extracted event data, not empty placeholders."""
    if not rfp or not rfp.active_ui_cards_json:
        return False
    cards = rfp.active_ui_cards_json
    overview = cards.get("event_overview", {}) or {}
    room = cards.get("room_block", {}) or {}
    meeting = cards.get("meeting_space", {}) or {}
    if not _is_placeholder_org(str(overview.get("company_name") or "")):
        return True
    if room.get("total_room_nights"):
        return True
    try:
        if int(meeting.get("headcount") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    cin = (overview.get("check_in_date") or "").strip()
    if cin and cin.upper() != "TBD":
        return True
    return False


def _user_confirms_booking(lower: str) -> bool:
    """Approval to book — not casual 'I want to book a room'."""
    if re.search(r"\b(book|reserve)\s+(a|the|one|my)\s+room", lower):
        return False
    if re.search(r"\b(want|like|need|would like|wanna)\s+to\s+(book|reserve)\b", lower):
        return False
    if any(w in lower for w in ("approve", "confirm", "looks good", "ready to book")):
        return True
    if re.search(r"\b(book it|book now|let'?s book|go ahead and book)\b", lower):
        return True
    return False


def _format_usd(amount: float | int | str | None) -> str | None:
    if amount is None:
        return None
    try:
        return f"${int(float(amount)):,}"
    except (TypeError, ValueError):
        return None


def _date_phrase(check_in: str | None, check_out: str | None) -> str | None:
    cin = (check_in or "").strip()
    cout = (check_out or "").strip()
    if not cin or cin.upper() == "TBD":
        return None
    if not cout or cout.upper() == "TBD":
        return f"starting {cin}"
    return f"from {cin} through {cout}"


def build_autonomous_voice_intro(rfp: RFPSubmission, *, partial: bool = False) -> str:
    cards = rfp.active_ui_cards_json or {}
    overview = cards.get("event_overview", {})
    if not overview.get("company_name") and not cards.get("room_block"):
        return ""

    meeting = cards.get("meeting_space", {})
    quote = cards.get("live_quote", {})
    room = cards.get("room_block", {})

    org = overview.get("company_name")
    event_type = (overview.get("event_type") or "").strip()
    nights = room.get("total_room_nights")
    headcount = meeting.get("headcount")
    try:
        headcount_n = int(headcount) if headcount is not None else 0
    except (TypeError, ValueError):
        headcount_n = 0

    parts: list[str] = []

    if partial:
        parts.append("I've drafted your request, but a few details still need confirmation on the cards.")
    else:
        parts.append("I've put together a draft summary on the right from what you shared.")

    detail_bits: list[str] = []
    if nights:
        n = int(nights)
        detail_bits.append(f"a {n}-night room block" if n != 1 else "a one-night stay")
    if not _is_placeholder_org(str(org or "")):
        detail_bits.insert(0, str(org))
    elif event_type and event_type.lower() not in {"corporate event", "event"}:
        detail_bits.insert(0, event_type)

    dates = _date_phrase(overview.get("check_in_date"), overview.get("check_out_date"))
    if dates:
        detail_bits.append(dates)
    if headcount_n > 0:
        detail_bits.append(f"meeting space for about {headcount_n} guests")

    if detail_bits:
        parts.append("So far I have " + ", ".join(detail_bits) + ".")

    rate = _format_usd(quote.get("anchor_price"))
    if rate:
        parts.append(f"Your preliminary package estimate is {rate} — see the quote card for details.")

    if not dates or headcount_n <= 0:
        missing: list[str] = []
        if not dates:
            missing.append("travel dates")
        if headcount_n <= 0:
            missing.append("group size")
        if missing:
            parts.append(
                "When you have a moment, add your "
                + " and ".join(missing)
                + " on the cards or tell me here."
            )

    parts.append("Say approve when you're ready, negotiate if you need different pricing, or ask to see the venue map.")
    return " ".join(parts)


def generate_voice_assistant_reply(
    message: str,
    *,
    rfp: RFPSubmission | None = None,
) -> str:
    cleaned = message.strip()
    if not cleaned:
        return (
            "Welcome. Tell me your dates, room nights, and meeting size, "
            "or upload an RFP with the plus button."
        )

    lower = cleaned.lower()
    if rfp:
        from .voice_card_updates import VoiceDateValidationError, apply_voice_message_to_cards

        try:
            applied = apply_voice_message_to_cards(str(rfp.id), cleaned)
        except VoiceDateValidationError as exc:
            return exc.message
        except Exception as exc:
            from apps.core.exceptions import CardMutationValidationError

            if isinstance(exc, CardMutationValidationError):
                return str(exc)
            raise
        if applied:
            rfp.refresh_from_db()
            meeting = applied.get("meeting_space") or {}
            room = applied.get("room_block") or {}
            overview = applied.get("event_overview") or {}
            bits: list[str] = []
            if overview.get("check_in_date") and overview.get("check_out_date"):
                bits.append(
                    f"your stay from {overview['check_in_date']} through {overview['check_out_date']}"
                )
            if room.get("peak_rooms"):
                bits.append(f"{room['peak_rooms']} rooms")
            if meeting.get("headcount"):
                bits.append(f"meeting headcount to {meeting['headcount']}")
            if room.get("total_room_nights") and not overview:
                n = int(room["total_room_nights"])
                bits.append(f"the room block to {n} night{'s' if n != 1 else ''}")
            if bits:
                return (
                    "Got it — I've updated "
                    + ", ".join(bits)
                    + ". Your quote card on the right is refreshed."
                )

    if rfp and rfp_has_meaningful_cards(rfp):
        cards = rfp.active_ui_cards_json
        overview = cards.get("event_overview", {})
        quote = cards.get("live_quote", {})
        org = overview.get("company_name")
        label = org if not _is_placeholder_org(str(org or "")) else "your event"

        if _user_confirms_booking(lower):
            rate = _format_usd(quote.get("anchor_price"))
            if rate:
                return (
                    f"Great — I'll prepare the proposal for {label} at the estimated rate of {rate} "
                    "shown on your quote card."
                )
            return f"Great — I'll prepare the proposal package for {label}."

        if any(w in lower for w in ("negotiate", "discount", "lower", "price", "better rate")):
            rate = _format_usd(quote.get("anchor_price"))
            if rate:
                return (
                    f"I can work with you on pricing around the {rate} estimate. "
                    "What budget or target rate are you aiming for?"
                )
            return "I'm refreshing your quote now — check the card on the right in a moment."

        if "map" in lower or "ballroom" in lower or "venue" in lower:
            return (
                "I'll highlight the venue map for you. "
                "The grand ballroom area is a strong fit for most corporate meetings."
            )
        if any(
            w in lower
            for w in (
                "summary",
                "recap",
                "what do you have",
                "run that back",
                "repeat",
                "read back",
            )
        ):
            return build_autonomous_voice_intro(rfp, partial=bool(rfp.amber_conflict_fields_json))

    if any(w in lower for w in ("hi", "hello", "hey")):
        if re.search(r"\bhow are you\b", lower):
            return (
                "I'm doing well, thank you. I'd love to help with your stay — "
                "what dates, how many nights, and how many guests are you planning?"
            )
        return (
            "Hi there. Share your event dates, room block, and headcount, "
            "or upload an RFP document to get started."
        )

    if re.search(r"\b(want|like|need|would like)\s+to\s+(book|reserve)\b", lower):
        return (
            "Absolutely — I can help you book. Tell me your check-in date, "
            "number of nights, and how many people, and I'll put together a package."
        )

    nights_match = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b", lower)
    if nights_match:
        return (
            "Got it. I'll use that for your room block — "
            "check the summary cards on the right and add anything that's missing."
        )

    return (
        "Thanks. Share a few more details — dates, room nights, and meeting size — "
        "or upload your full RFP and I'll build the summary for you."
    )


def quick_voice_ack(message: str) -> str:
    """Short spoken line while the assistant continues processing."""
    cleaned = message.strip()
    if not cleaned:
        return "I'm listening — go ahead with your event details."

    lower = cleaned.lower()
    bits: list[str] = []

    people = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*"
        r"(people|peoples|persons|guests|attendees|pax)\b",
        lower,
    )
    if people:
        bits.append(f"{people.group(1)} guests")

    nights = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b",
        lower,
    )
    if nights:
        bits.append(f"{nights.group(1)} nights")

    if re.search(r"\b(next month|january|february|march|april|may|june|july|august|"
                 r"september|october|november|december|\d{1,2}(st|nd|rd|th)?)\b", lower):
        bits.append("those dates")

    if "map" in lower or "ballroom" in lower or "venue" in lower:
        bits.append("the venue map")

    if bits:
        return "Got it — " + ", ".join(bits) + ". I'm pulling that together now."
    if len(cleaned) > 120:
        return "Thanks for the detail — I'm reading through that now."
    return "Got it — one moment while I work on that for you."


def progressive_status_messages(message: str, *, rfp: RFPSubmission | None = None) -> list[str]:
    """Mid-flight status lines for streaming UX."""
    lower = message.lower()
    lines = ["Reviewing dates, room block, and meeting needs…"]
    if rfp and rfp.active_ui_cards_json:
        lines.append("Updating your summary cards on the right…")
    elif any(w in lower for w in ("room", "night", "headcount", "ballroom", "catering")):
        lines.append("Matching your request to our packages…")
    lines.append("Almost ready…")
    return lines
