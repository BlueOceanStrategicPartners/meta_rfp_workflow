import pytest

from apps.negotiation_agent.voice_scenario import build_autonomous_voice_intro, generate_voice_assistant_reply
from apps.rfp_debate.card_normalize import normalize_cards_for_ui
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_voice_intro_avoids_internal_jargon(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="Two nights",
        active_ui_cards_json={
            "live_quote": {"anchor_price": 297, "floor_price": 280},
        },
    )
    normalize_cards_for_ui(rfp)
    intro = build_autonomous_voice_intro(rfp)
    lower = intro.lower()
    assert "three-agent" not in lower
    assert "walk-away" not in lower
    assert "floor" not in lower
    assert "voice rfp session" not in lower
    assert "297" in intro or "$297" in intro


@pytest.mark.django_db
def test_book_a_room_is_not_approval(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {"company_name": "Your organization"},
            "meeting_space": {"headcount": 0},
            "live_quote": {"anchor_price": 297, "floor_price": 280},
        },
    )
    normalize_cards_for_ui(rfp)
    reply = generate_voice_assistant_reply(
        "Hi, how are you doing today? I want to book a room.",
        rfp=rfp,
    )
    lower = reply.lower()
    assert "prepare the proposal" not in lower
    assert "297" not in reply


@pytest.mark.django_db
def test_greeting_and_book_room_without_meaningful_cards(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="Hi book a room",
        active_ui_cards_json={"event_overview": {}, "room_block": {}},
    )
    normalize_cards_for_ui(rfp)
    reply = generate_voice_assistant_reply("Hi, how are you? I want to book a room.", rfp=rfp)
    assert "how many" in reply.lower() or "dates" in reply.lower()


@pytest.mark.django_db
def test_negotiate_reply_hides_floor(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {"company_name": "Acme Corp"},
            "live_quote": {"anchor_price": 297, "floor_price": 280},
        },
    )
    reply = generate_voice_assistant_reply("Can you lower the price?", rfp=rfp)
    assert "floor" not in reply.lower()
    assert "anchor" not in reply.lower()
