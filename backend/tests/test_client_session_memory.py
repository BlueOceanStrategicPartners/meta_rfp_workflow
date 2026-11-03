import pytest

from apps.negotiation_agent.client_session_memory import (
    MAX_TRANSCRIPT_TURNS,
    append_session_event,
    build_agent_context_block,
    build_card_mutation_ack,
    normalize_session,
    record_assistant_reply,
    sync_clarifications_from_cards,
    summarize_cards_for_agent,
)
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_append_session_event_caps_events(client_user):
    rfp = RFPSubmission.objects.create(client=client_user, client_session_json={})
    for i in range(45):
        append_session_event(rfp, event_type="voice", summary=f"line {i}")
    rfp.save(update_fields=["client_session_json"])
    session = normalize_session(rfp.client_session_json)
    assert len(session["events"]) == 40
    assert session["events"][-1]["summary"] == "line 44"


@pytest.mark.django_db
def test_normalize_session_preserves_transcript():
    raw = {
        "transcript": [
            {"role": "user", "text": "Hello", "at": "2026-01-01T00:00:00+00:00"},
            {"role": "assistant", "text": "Hi there", "at": "2026-01-01T00:00:01+00:00"},
            {"role": "bot", "text": "ignored", "at": "x"},
        ],
    }
    session = normalize_session(raw)
    assert len(session["transcript"]) == 2
    assert session["transcript"][0]["role"] == "user"


@pytest.mark.django_db
def test_record_assistant_reply_appends_transcript_and_event(client_user):
    rfp = RFPSubmission.objects.create(client=client_user, client_session_json={})
    record_assistant_reply(rfp, "We can adjust your room block.")
    session = normalize_session(rfp.client_session_json)
    assert session["transcript"][-1]["role"] == "assistant"
    assert "room block" in session["transcript"][-1]["text"]
    assert session["events"][-1]["type"] == "assistant_reply"


@pytest.mark.django_db
def test_transcript_caps_at_max_turns(client_user):
    rfp = RFPSubmission.objects.create(client=client_user, client_session_json={})
    for i in range(MAX_TRANSCRIPT_TURNS + 5):
        record_assistant_reply(rfp, f"reply {i}")
    session = normalize_session(rfp.client_session_json)
    assert len(session["transcript"]) == MAX_TRANSCRIPT_TURNS
    assert session["transcript"][-1]["text"] == f"reply {MAX_TRANSCRIPT_TURNS + 4}"


@pytest.mark.django_db
def test_build_agent_context_block_includes_transcript_dialogue(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"event_overview": {"company_name": "Acme"}},
        client_session_json={
            "transcript": [
                {"role": "user", "text": "Need 40 guests", "at": "t1"},
                {"role": "assistant", "text": "Noted forty guests.", "at": "t2"},
            ],
        },
    )
    block = build_agent_context_block(rfp)
    assert "Recent dialogue:" in block
    assert "Client: Need 40 guests" in block
    assert "Assistant: Noted forty guests." in block


@pytest.mark.django_db
def test_sync_clarifications_marks_done_when_filled(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {
                "check_in_date": "2026-08-01",
                "check_out_date": "2026-08-03",
                "amber_fields": ["check_in_date"],
            },
            "room_block": {"total_room_nights": 2, "amber_fields": ["total_room_nights"]},
            "meeting_space": {"headcount": 50},
        },
    )
    sync_clarifications_from_cards(rfp)
    todos = {t["id"]: t["status"] for t in rfp.client_session_json["agent_todos"]}
    assert todos.get("dates") == "done"
    assert todos.get("nights") == "done"
    assert "headcount" not in todos


@pytest.mark.django_db
def test_sync_clarifications_pending_headcount(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {"check_in_date": "2026-08-01", "check_out_date": "2026-08-03"},
            "room_block": {"total_room_nights": 2},
            "meeting_space": {"headcount": 0},
        },
    )
    sync_clarifications_from_cards(rfp)
    session = rfp.client_session_json
    assert any("headcount" in t["text"].lower() for t in session["agent_todos"])
    assert session["clarification_options"]


@pytest.mark.django_db
def test_summarize_cards_excludes_floor(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {"company_name": "Acme", "check_in_date": "2026-08-01"},
            "live_quote": {"anchor_price": "12000", "floor_price": "9000"},
        },
        status="NEGOTIATING",
    )
    text = summarize_cards_for_agent(rfp)
    assert "Acme" in text
    assert "12000" in text
    assert "9000" not in text


@pytest.mark.django_db
def test_build_agent_context_block_includes_recent(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"event_overview": {"company_name": "Acme"}},
        client_session_json={
            "events": [{"type": "card_edit", "summary": "Updated headcount 40"}],
            "clarification_options": [],
            "agent_todos": [],
        },
    )
    block = build_agent_context_block(rfp)
    assert "CLIENT SESSION MEMORY" in block
    assert "Updated headcount" in block
    assert "Acme" in block


def test_build_card_mutation_ack():
    patch = {"meeting_space": {"headcount": 25}}
    cards = {"live_quote": {"anchor_price": "15000"}}
    msg = build_card_mutation_ack(patch, cards)
    assert "25" in msg
    assert "15000" in msg


@pytest.mark.django_db
def test_validate_card_mutation_broadcasts_session(client_user, monkeypatch):
    from apps.ui_card_validator.services import validate_card_mutation

    broadcasts: list[tuple] = []

    def capture(sid, msg_type, payload):
        broadcasts.append((msg_type, payload))

    monkeypatch.setattr("apps.ui_card_validator.services.broadcast_rfp", capture)

    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "event_overview": {"check_in_date": "2027-09-01", "check_out_date": "2027-09-03"},
            "room_block": {"blocks": [], "total_room_nights": 2},
            "meeting_space": {"headcount": 40, "seating_style": "classroom"},
        },
    )
    result = validate_card_mutation(
        str(rfp.id),
        {"meeting_space": {"headcount": 35}},
    )
    assert result["ok"] is True
    types = [b[0] for b in broadcasts]
    assert "cards_patch" in types
    assert "agent_utterance" in types
    assert "client_session_patch" in types
    rfp.refresh_from_db()
    assert rfp.client_session_json.get("events")
