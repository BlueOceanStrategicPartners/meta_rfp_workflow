import pytest

from apps.negotiation_agent.client_session_memory import normalize_session, record_voice_turn
from apps.negotiation_agent.voice_card_updates import parse_room_nights_from_block_phrase, parse_voice_card_patch
from apps.negotiation_agent.voice_intake_apply import apply_intake_classification_to_cards
from apps.negotiation_agent.voice_intake_gates import run_intake_gate_pipeline
from apps.rfp_debate.models import RFPSubmission


def test_parse_room_nights_from_block_phrase():
    assert parse_room_nights_from_block_phrase("We need a 3-night room block") == 3
    assert parse_room_nights_from_block_phrase("three nights room block") == 3


@pytest.mark.django_db
def test_planning_patch_includes_block_nights(client_user):
    msg = "Hi, we need 5 guests for meeting space and a 3-night room block."
    patch = parse_voice_card_patch(msg)
    assert patch is not None
    assert patch.get("room_block", {}).get("total_room_nights") == 3


@pytest.mark.django_db
def test_gate_applies_checkout_one_day_to_cards(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"meeting_space": {"headcount": 5}},
        client_session_json={},
    )
    from datetime import date
    from unittest.mock import patch

    msg = "Only one day we are in so November 9 we will check out"
    with patch("apps.negotiation_agent.voice_dates.voice_today", return_value=date(2026, 11, 4)):
        result = run_intake_gate_pipeline(rfp, msg)
    assert result is not None
    assert not isinstance(result, str)
    assert "how many nights" not in result.spoken.lower()
    rfp.refresh_from_db()
    overview = (rfp.active_ui_cards_json or {}).get("event_overview") or {}
    assert overview.get("check_in_date") == "2026-11-08"
    assert overview.get("check_out_date") == "2026-11-09"
    assert (rfp.active_ui_cards_json or {}).get("room_block", {}).get("total_room_nights") == 1


@pytest.mark.django_db
def test_llm_classification_applies_stay_to_cards(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"meeting_space": {"headcount": 5}},
        client_session_json={},
    )
    raw = {
        "intent": "set_stay_complete",
        "check_in_iso": "2026-11-08",
        "nights": 1,
        "confidence": 0.88,
        "reply": "Got it — one night.",
    }
    assert apply_intake_classification_to_cards(rfp, raw) is True
    rfp.refresh_from_db()
    overview = (rfp.active_ui_cards_json or {}).get("event_overview") or {}
    assert overview.get("check_out_date") == "2026-11-09"


@pytest.mark.django_db
def test_record_voice_turn_strips_undefined_prefix(client_user):
    rfp = RFPSubmission.objects.create(client=client_user, client_session_json={})
    record_voice_turn(rfp, "undefinedHi there")
    session = normalize_session(rfp.client_session_json)
    assert session["transcript"][-1]["text"] == "Hi there"
    assert "undefined" not in session["events"][-1]["summary"]
