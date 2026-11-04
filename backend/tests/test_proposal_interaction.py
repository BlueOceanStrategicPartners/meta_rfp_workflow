import pytest

from apps.designer_studio.proposal_bindings import (
    ensure_client_bridge_script_tag,
    inject_proposal_client_bridge,
)
from apps.negotiation_agent.proposal_interaction import filter_card_patch, handle_proposal_interaction
from apps.rfp_debate.models import RFPStatus, RFPSubmission


def test_filter_card_patch_whitelist():
    raw = {
        "room_block": {"peak_rooms": 10},
        "evil": {"x": 1},
        "event_overview": {"check_in_date": "2027-06-01"},
    }
    out = filter_card_patch(raw)
    assert "evil" not in out
    assert out["room_block"]["peak_rooms"] == 10


def test_inject_proposal_client_bridge_once():
    html = "<!DOCTYPE html><html><body><p>x</p></body></html>"
    once = inject_proposal_client_bridge(html)
    assert "rfpProposalEmit" in once
    twice = inject_proposal_client_bridge(once)
    assert twice.count("data-proposal-client-bridge") == 1


def test_ensure_client_bridge_script_tag():
    html = "<html><body></body></html>"
    out = ensure_client_bridge_script_tag(html)
    assert "proposal_client_bridge.js" in out


@pytest.mark.django_db
def test_handle_proposal_interaction_event_only(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={"event_overview": {}, "room_block": {}, "meeting_space": {}},
    )
    result = handle_proposal_interaction(
        str(rfp.id),
        {"kind": "event", "action": "navigate", "label": "Opened pricing section"},
    )
    assert result["ok"] is True
    assert result.get("event_only") is True
    rfp.refresh_from_db()
    types = [e.get("type") for e in rfp.client_session_json.get("events") or []]
    assert "proposal_interaction" in types


@pytest.mark.django_db
def test_handle_proposal_interaction_mutation(client_user, monkeypatch):
    broadcasts: list[tuple] = []

    def capture(sid, msg_type, payload):
        broadcasts.append((msg_type, payload))

    monkeypatch.setattr("apps.ui_card_validator.services.broadcast_rfp", capture)
    monkeypatch.setattr("apps.negotiation_agent.proposal_interaction.broadcast_rfp", capture)

    rendered = []

    def fake_render(rfp):
        rendered.append(str(rfp.id))
        return "<html>ok</html>"

    monkeypatch.setattr(
        "apps.negotiation_agent.proposal_render.render_proposal_for_rfp",
        fake_render,
    )

    rfp = RFPSubmission.objects.create(
        client=client_user,
        status=RFPStatus.PROPOSAL_RENDERED,
        active_ui_cards_json={
            "event_overview": {"check_in_date": "2027-09-01", "check_out_date": "2027-09-03"},
            "room_block": {"total_room_nights": 2, "peak_rooms": 5},
            "meeting_space": {"headcount": 40, "seating_style": "classroom"},
        },
    )
    result = handle_proposal_interaction(
        str(rfp.id),
        {
            "kind": "mutation",
            "action": "adjust_rooms",
            "label": "Set peak rooms to 8",
            "cardPatch": {"room_block": {"peak_rooms": 8}},
        },
    )
    assert result["ok"] is True
    assert rendered
    rfp.refresh_from_db()
    assert rfp.active_ui_cards_json["room_block"]["peak_rooms"] == 8
