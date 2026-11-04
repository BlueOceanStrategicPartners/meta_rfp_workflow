from apps.negotiation_agent.meeting_space_intent import (
    message_declines_meeting_space,
    meeting_space_wanted,
    try_apply_meeting_space_decline,
)
from apps.rfp_debate.models import RFPSubmission


def test_decline_detects_speech_typo():
    assert message_declines_meeting_space("We don't want the meat in space.")


def test_decline_clears_meeting_card(db, client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {"check_in_date": "2026-11-15", "check_out_date": "2026-11-16"},
            "room_block": {"peak_rooms": 3, "total_room_nights": 1},
            "meeting_space": {"headcount": 3},
        },
        client_session_json={},
    )
    assert try_apply_meeting_space_decline(rfp, "no meeting space please")
    rfp.refresh_from_db()
    assert rfp.active_ui_cards_json["meeting_space"]["included"] is False
    assert rfp.active_ui_cards_json["meeting_space"].get("headcount") is None
    assert rfp.client_session_json["intake"]["needs_meeting_space"] == "0"
    assert meeting_space_wanted(rfp) is False
