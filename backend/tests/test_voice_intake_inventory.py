from datetime import date
from unittest.mock import patch

import pytest

from apps.inventory.models import HistoricalOccupancy, VenueProperty
from apps.inventory.room_availability import ensure_occupancy_rows
from apps.negotiation_agent.voice_intake_gates import run_intake_gate_pipeline
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_intake_rejects_100_rooms_when_only_86_free(client_user):
    prop = VenueProperty.objects.create(name="Inventory Hotel")
    check_in = date(2026, 11, 10)
    ensure_occupancy_rows(prop, check_in, 1)
    HistoricalOccupancy.objects.filter(property=prop, target_date=check_in).update(
        room_occupancy_pct=0.73125,
    )

    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "meeting_space": {"headcount": 100},
            "room_block": {"peak_rooms": 100},
            "live_quote": {"anchor_price": "1", "floor_price": "1"},
        },
        client_session_json={
            "intake": {
                "availability_window_start": "2026-11-09",
                "availability_window_days": "7",
            }
        },
    )
    msg = "So can we take up 100 rooms in Tuesday?"
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 3)):
        result = run_intake_gate_pipeline(rfp, msg)
    assert result is not None
    assert not isinstance(result, str)
    spoken = result.spoken
    assert "86" in spoken
    assert "can't hold" in spoken.lower()
    assert "Yes — we can work toward" not in spoken


@pytest.mark.django_db
def test_tuesday_group_block_uses_next_week_not_today(client_user):
    VenueProperty.objects.create(name="Week Hotel")
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "meeting_space": {"headcount": 100},
            "room_block": {"peak_rooms": 100},
            "live_quote": {"anchor_price": "1", "floor_price": "1"},
        },
    )
    msg = "We need Tuesday but our participant count is 100 and each need a one room."
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 3)):
        result = run_intake_gate_pipeline(rfp, msg)
    assert result is not None
    assert not isinstance(result, str)
    assert "November 03" not in result.spoken
    assert "November 10" in result.spoken or "Tuesday" in result.spoken
