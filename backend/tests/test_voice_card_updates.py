import pytest

from apps.negotiation_agent.voice_card_updates import parse_voice_card_patch
from apps.negotiation_agent.voice_scenario import generate_voice_assistant_reply
from apps.rfp_debate.card_normalize import normalize_cards_for_ui
from apps.rfp_debate.models import RFPSubmission


def test_parse_headcount_correction():
    patch = parse_voice_card_patch("but headcount is not 50, it is 20")
    assert patch == {"meeting_space": {"headcount": 20}}


def test_parse_catering_and_av_from_voice():
    msg = "We need continental breakfast and a projector with screen for the meeting."
    patch = parse_voice_card_patch(msg)
    assert patch is not None
    assert "continental breakfast" in (patch.get("catering_av") or {}).get("catering", "").lower()
    assert (patch.get("catering_av") or {}).get("av")
    assert (patch.get("meeting_space") or {}).get("av")


def test_parse_seating_style_from_voice():
    patch = parse_voice_card_patch("Please switch meeting seating to theater style for 40 people")
    assert patch is not None
    assert (patch.get("meeting_space") or {}).get("seating_style") == "theater"
    assert (patch.get("meeting_space") or {}).get("headcount") == 40


@pytest.mark.django_db
def test_voice_correction_updates_reply(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="Event",
        active_ui_cards_json={
            "event_overview": {"company_name": "Your organization"},
            "room_block": {"total_room_nights": 3},
            "meeting_space": {"headcount": 50, "seating_style": "classroom"},
            "live_quote": {"anchor_price": "297", "floor_price": "280"},
        },
    )
    normalize_cards_for_ui(rfp)
    reply = generate_voice_assistant_reply("but headcount is not 50, it is 20", rfp=rfp)
    rfp.refresh_from_db()
    assert rfp.active_ui_cards_json["meeting_space"]["headcount"] == 20
    assert "20" in reply
    assert "50 guests" not in reply
