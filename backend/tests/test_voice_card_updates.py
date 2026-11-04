import pytest

from apps.negotiation_agent.voice_card_updates import parse_voice_card_patch
from apps.negotiation_agent.voice_scenario import generate_voice_assistant_reply
from apps.rfp_debate.card_normalize import normalize_cards_for_ui
from apps.rfp_debate.models import RFPSubmission


def test_parse_headcount_correction():
    patch = parse_voice_card_patch("but headcount is not 50, it is 20")
    assert (patch.get("meeting_space") or {}).get("headcount") == 20


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


def test_headcount_from_classroom_setup_without_guests_keyword():
    msg = (
        "Blue Ocean events room block for 85 check in June 17 check out June 19 "
        "two night corporate training meeting space for about 85 in classroom setup"
    )
    patch = parse_voice_card_patch(msg)
    assert patch is not None
    assert (patch.get("meeting_space") or {}).get("headcount") == 85
    assert (patch.get("meeting_space") or {}).get("seating_style") == "classroom"


def test_room_block_485_attend_asr():
    msg = (
        "hi we are Blue Ocean events we need a room block 485 attend this "
        "check in Monday June 17 and check out June 19 two nights classroom setup"
    )
    patch = parse_voice_card_patch(msg)
    assert patch is not None
    assert (patch.get("meeting_space") or {}).get("headcount") == 85
    assert (patch.get("room_block") or {}).get("peak_rooms") == 85


def test_room_lock_for_headcount_asr_typo():
    patch = parse_voice_card_patch("We need a room lock for 85 next week")
    assert patch is not None
    assert (patch.get("meeting_space") or {}).get("headcount") == 85


def test_guest_count_ignores_year_in_stay_phrase():
    patch = parse_voice_card_patch(
        "Corporate offsite, 5 guests, arriving March 10 2026 for one night. Theater seating."
    )
    assert patch is not None
    assert (patch.get("meeting_space") or {}).get("headcount") == 5
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
