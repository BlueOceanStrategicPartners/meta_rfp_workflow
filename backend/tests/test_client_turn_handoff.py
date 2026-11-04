import pytest

from apps.negotiation_agent.client_session_memory import build_agent_context_block, normalize_session
from apps.negotiation_agent.client_turn_handoff import (
    build_turn_handoff,
    client_message_signals_repeat_frustration,
    derive_gathered_facts,
    refresh_turn_handoff,
    spoken_recap_from_handoff,
)
from apps.negotiation_agent.voice_assistant import generate_voice_assistant_reply_for_rfp
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_derive_gathered_from_transcript_and_cards(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {},
            "room_block": {"total_room_nights": 3},
            "meeting_space": {"headcount": 0, "seating_style": "classroom"},
        },
        client_session_json={
            "transcript": [
                {"role": "user", "text": "We need 5 attendees for the meeting", "at": "t1"},
            ],
            "intake": {"headcount": "5"},
        },
    )
    gathered = derive_gathered_facts(rfp)
    assert gathered.get("headcount") == 5
    assert gathered.get("room_nights") == 3


@pytest.mark.django_db
def test_turn_handoff_still_needs_check_in(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "room_block": {"total_room_nights": 3},
            "meeting_space": {"headcount": 5},
        },
        client_session_json={},
    )
    handoff = build_turn_handoff(rfp)
    assert handoff["gathered"].get("headcount") == 5
    assert "check_in_date" in handoff["still_needed"]
    assert handoff["ask_next"]


@pytest.mark.django_db
def test_build_agent_context_includes_handoff_json(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"meeting_space": {"headcount": 12}},
        client_session_json={},
    )
    refresh_turn_handoff(rfp)
    block = build_agent_context_block(rfp)
    assert "NEXT TURN HANDOFF" in block
    assert "headcount" in block


@pytest.mark.django_db
def test_frustration_message_recap(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "room_block": {"total_room_nights": 3},
            "meeting_space": {"headcount": 5},
        },
        client_session_json={
            "transcript": [
                {"role": "user", "text": "5 attendees and 3 nights", "at": "t1"},
            ],
        },
    )
    assert client_message_signals_repeat_frustration("Checking this, I already told you.")
    recap = spoken_recap_from_handoff(rfp)
    assert "5 guests" in recap
    assert "3 night" in recap
    assert "check-in" in recap.lower() or "?" in recap


@pytest.mark.django_db
def test_voice_reply_frustration_short_circuit(client_user, monkeypatch):
    monkeypatch.setattr(
        "apps.negotiation_agent.voice_assistant.is_social_greeting",
        lambda _m: False,
    )
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "room_block": {"total_room_nights": 3},
            "meeting_space": {"headcount": 5},
        },
        client_session_json={},
    )
    reply = generate_voice_assistant_reply_for_rfp(
        "Checking this, I already told you.",
        rfp=rfp,
    )
    assert "You're right" in reply or "on record" in reply
    session = normalize_session(rfp.client_session_json)
    assert session.get("turn_handoff")
