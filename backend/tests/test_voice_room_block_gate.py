from datetime import date

import pytest

from apps.inventory.models import HistoricalOccupancy, VenueProperty
from apps.inventory.room_availability import ensure_occupancy_rows
from apps.negotiation_agent.voice_room_block_gate import try_room_block_capacity_reply
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_room_block_exceeds_inventory_spoken(client_user):
    prop = VenueProperty.objects.create(name="Gate Hotel")
    check_in = date(2026, 11, 11)
    ensure_occupancy_rows(prop, check_in, 1)
    HistoricalOccupancy.objects.filter(property=prop, target_date=check_in).update(
        room_occupancy_pct=0.73125,
    )

    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "meeting_space": {"headcount": 100},
            "room_block": {"peak_rooms": 100},
            "event_overview": {"check_in_date": check_in.isoformat()},
            "live_quote": {"anchor_price": "1", "floor_price": "1"},
        },
    )
    msg = (
        "but one issue we have a hundred gates now you know it but each one want a solar room "
        "so everyone need a total hundred rooms"
    )
    reply = try_room_block_capacity_reply(rfp, msg)
    assert reply is not None
    assert "86" in reply or "only have about" in reply.lower()
    assert "can't hold" in reply.lower() or "can't hold" in reply
    assert "100" in reply
