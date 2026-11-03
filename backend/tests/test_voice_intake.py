from datetime import date
from unittest.mock import patch

import pytest

from apps.negotiation_agent.voice_dates import (
    parse_arrival_date_from_voice,
    parse_weekday_index,
    resolve_weekday_in_window,
)
from apps.negotiation_agent.voice_intake import record_availability_window, try_voice_intake_followup
from apps.rfp_debate.models import RFPSubmission


FIXED_TODAY = date(2026, 11, 3)  # Tuesday
WINDOW_START = date(2026, 11, 9)  # Monday (next week table)


def test_parse_weekday_index():
    assert parse_weekday_index("Can you allow us to come Tuesday") == 1


def test_resolve_tuesday_in_availability_window():
    resolved = resolve_weekday_in_window(1, WINDOW_START, 7)
    assert resolved == date(2026, 11, 10)


def test_parse_arrival_uses_window():
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        arrival = parse_arrival_date_from_voice(
            "We would like to come on Tuesday",
            availability_window_start=WINDOW_START,
        )
    assert arrival == date(2026, 11, 10)


@pytest.mark.django_db
def test_intake_followup_after_tuesday(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="Event",
        active_ui_cards_json={
            "event_overview": {"company_name": "Your organization"},
            "room_block": {},
            "meeting_space": {},
            "live_quote": {},
        },
    )
    record_availability_window(
        rfp,
        {"window_start_iso": WINDOW_START.isoformat(), "window_days": 7, "rows": []},
    )
    rfp.save()

    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        reply = try_voice_intake_followup(
            rfp,
            "You be allowed to come Tuesday.",
        )

    assert reply is not None
    assert "November 10" in reply or "Nov 10" in reply or "Tuesday" in reply
    assert "night" in reply.lower()
    assert "future date" not in reply.lower()
    assert "which" not in reply.lower() or "how many" in reply.lower()


@pytest.mark.django_db
def test_intake_nights_after_pending_arrival(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="Event",
        client_session_json={
            "intake": {
                "check_in_iso": "2026-11-10",
                "pending_field": "nights",
            }
        },
        active_ui_cards_json={
            "event_overview": {"company_name": "Your organization", "check_in_date": "2026-11-10"},
            "room_block": {},
            "meeting_space": {},
            "live_quote": {"anchor_price": "100", "floor_price": "90"},
        },
    )

    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        reply = try_voice_intake_followup(rfp, "Three nights please.")

    assert reply is not None
    assert "3 night" in reply.lower()
    rfp.refresh_from_db()
    assert rfp.active_ui_cards_json["room_block"]["total_room_nights"] == 3
