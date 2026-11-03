from datetime import date
from unittest.mock import patch

import pytest

from apps.negotiation_agent.voice_intake_gates import run_intake_gate_pipeline
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_gate_arrival_pending_nights(client_user):
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
    msg = "If we allow to come Tuesday, 100 need 100 rooms."
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 3)):
        result = run_intake_gate_pipeline(rfp, msg)
    assert result is not None
    assert not isinstance(result, str)
    assert "night" in result.spoken.lower()
    assert "100" in result.spoken
