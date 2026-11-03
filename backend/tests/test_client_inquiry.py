from datetime import date
from unittest.mock import patch

import pytest

from apps.negotiation_agent.client_inquiry import try_client_planning_response
from apps.inventory.models import VenueProperty
from apps.rfp_debate.models import RFPSubmission

SAMPLE = (
    "We need a room next week, actually not one room. We need several rooms. "
    "We have 100 participants. So how about your rooms? What kind of rooms you have?"
)

FIXED_TODAY = date(2026, 11, 3)


@pytest.mark.django_db
def test_planning_turn_answers_group_rooms_and_next_week(client_user):
    VenueProperty.objects.create(name="Planning Hotel")
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="Event",
        active_ui_cards_json={
            "event_overview": {"company_name": "Your organization"},
            "room_block": {},
            "meeting_space": {},
            "live_quote": {"anchor_price": "100", "floor_price": "90"},
        },
    )
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=FIXED_TODAY):
        result = try_client_planning_response(rfp, SAMPLE)
    assert result is not None
    spoken, ui = result
    lower = spoken.lower()
    assert "100" in spoken
    assert "king" in lower or "queen" in lower or "guest" in lower
    assert "next week" in lower or "inventory" in lower
    assert "draft summary" not in lower
    assert "add your travel dates and group size" not in lower
    assert ui is not None
    assert ui.get("type") == "availability_table"
    rfp.refresh_from_db()
    assert rfp.active_ui_cards_json["meeting_space"]["headcount"] == 100
    assert rfp.active_ui_cards_json["room_block"]["peak_rooms"] == 100
