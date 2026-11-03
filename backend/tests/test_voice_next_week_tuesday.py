from datetime import date
from unittest.mock import patch

import pytest

from apps.inventory.models import VenueProperty
from apps.inventory.room_availability import build_availability_table, spoken_availability_for_message
from apps.negotiation_agent.voice_dates import parse_arrival_date_from_voice
from apps.negotiation_agent.voice_intake_gates import run_intake_gate_pipeline
from apps.negotiation_agent.client_inquiry import detect_planning_turn
from apps.rfp_debate.models import RFPSubmission


def test_next_week_tuesday_resolves_to_calendar_tuesday():
    msg = "We will arrive next week Tuesday."
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 3)):
        resolved = parse_arrival_date_from_voice(msg)
    assert resolved is not None
    assert resolved.weekday() == 1  # Tuesday
    assert resolved.isoformat() == "2026-11-10"


def test_arrival_only_not_planning_turn():
    assert detect_planning_turn("We will arrive next week Tuesday.") is False


@pytest.mark.django_db
def test_intake_confirms_tuesday_not_monday(client_user):
    VenueProperty.objects.create(name="Week Hotel")
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"live_quote": {"anchor_price": "1", "floor_price": "1"}},
    )
    msg = "We will arrive next week Tuesday."
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 3)):
        result = run_intake_gate_pipeline(rfp, msg)
    assert result is not None
    assert not isinstance(result, str)
    assert "Tuesday" in result.spoken
    assert "Mon" not in result.spoken.split("Tuesday")[0]


@pytest.mark.django_db
def test_spoken_availability_uses_named_weekday(db):
    prop = VenueProperty.objects.create(name="Table Hotel")
    with patch("apps.inventory.room_availability.timezone.localdate", return_value=date(2026, 11, 3)):
        table = build_availability_table(property=prop)
    msg = "We will arrive next week Tuesday."
    spoken = spoken_availability_for_message(table, msg)
    assert "Tuesday" in spoken
    assert "Mon, Nov 09 looks strongest" not in spoken
