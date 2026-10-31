from datetime import date
from unittest.mock import patch

import pytest

from apps.negotiation_agent.voice_card_updates import parse_voice_card_patch
from apps.negotiation_agent.voice_dates import parse_stay_dates_from_voice, validate_stay_not_in_past

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


def test_reject_past_check_in():
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        err = validate_stay_not_in_past(date(2026, 10, 1), date(2026, 10, 3))
    assert err is not None
    assert "past" in err.lower()
