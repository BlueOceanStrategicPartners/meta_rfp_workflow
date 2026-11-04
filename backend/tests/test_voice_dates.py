from datetime import date
from unittest.mock import patch

import pytest

from apps.negotiation_agent.voice_card_updates import parse_voice_card_patch
from apps.negotiation_agent.voice_dates import (
    parse_stay_dates_from_voice,
    parse_stay_from_checkout_and_duration,
    validate_stay_not_in_past,
)
from apps.negotiation_agent.voice_intake_gates import run_intake_gate_pipeline
from apps.rfp_debate.models import RFPSubmission

FIXED_TODAY = date(2026, 10, 28)


@pytest.mark.django_db
def test_parse_arrive_27_depart_29():
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        stay = parse_stay_dates_from_voice(
            "I will arrive 27th morning and the departure will be 29th. We need 3 rooms."
        )
        assert stay is not None
        check_in, check_out = stay
        assert check_in == date(2026, 11, 27)
        assert check_out == date(2026, 11, 29)


def test_parse_voice_patch_includes_dates_and_rooms():
    msg = "I will arrive 27th morning and the departure will be 29th. We need 3 rooms."
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        patch_payload = parse_voice_card_patch(msg)
    assert patch_payload is not None
    assert patch_payload["event_overview"]["check_in_date"] == "2026-11-27"
    assert patch_payload["room_block"]["peak_rooms"] == 3


def test_checkout_one_day_stay_not_asked_nights():
    msg = "Only one day we are in so November 9 we will check out"
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 4)):
        stay = parse_stay_from_checkout_and_duration(msg)
        assert stay is not None
        check_in, check_out = stay
        assert check_out == date(2026, 11, 9)
        assert check_in == date(2026, 11, 8)
        patch_payload = parse_voice_card_patch(msg)
    assert patch_payload is not None
    assert patch_payload["event_overview"]["check_out_date"] == "2026-11-09"
    assert patch_payload["event_overview"]["check_in_date"] == "2026-11-08"
    assert patch_payload["room_block"]["total_room_nights"] == 1


@pytest.mark.django_db
def test_gate_does_not_reask_nights_when_one_day_checkout(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"meeting_space": {"headcount": 5}},
        client_session_json={},
    )
    msg = "Only one day we are in so November 9 we will check out"
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 4)):
        result = run_intake_gate_pipeline(rfp, msg)
    assert result is None or (
        not isinstance(result, str) and "how many nights" not in result.spoken.lower()
    )


def test_reject_past_check_in():
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        err = validate_stay_not_in_past(date(2026, 10, 1), date(2026, 10, 3))
    assert err is not None
    assert "past" in err.lower()
