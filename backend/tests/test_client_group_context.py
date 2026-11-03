import pytest
from datetime import date
from unittest.mock import patch

from apps.negotiation_agent.client_group_context import (
    persist_group_size_to_intake,
    resolve_stored_headcount,
    spoken_headcount_confirm,
)
from apps.negotiation_agent.voice_intake import try_voice_intake_followup
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_headcount_persists_in_intake_and_transcript(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="100 participants",
        client_session_json={
            "transcript": [{"role": "user", "text": "We have 100 participants.", "at": "t"}]
        },
        active_ui_cards_json={
            "event_overview": {},
            "room_block": {},
            "meeting_space": {},
            "live_quote": {},
        },
    )
    persist_group_size_to_intake(rfp, headcount=100, peak_rooms=100)
    rfp.save()
    assert resolve_stored_headcount(rfp) == 100


@pytest.mark.django_db
def test_date_followup_confirms_stored_headcount(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {},
            "room_block": {},
            "meeting_space": {"headcount": 100},
            "live_quote": {"anchor_price": "1", "floor_price": "1"},
        },
        client_session_json={
            "intake": {
                "headcount": "100",
                "peak_rooms": "100",
                "availability_window_start": "2026-11-09",
                "availability_window_days": "7",
            },
            "transcript": [{"role": "user", "text": "100 participants", "at": "t"}],
        },
    )
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 3)):
        reply = try_voice_intake_followup(rfp, "We would like to arrive on Tuesday.")
    assert reply is not None
    assert "100 participants" in reply
    assert spoken_headcount_confirm(100).split(".")[0] in reply
    assert "how many participants" not in reply.lower()
