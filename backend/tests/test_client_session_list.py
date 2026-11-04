import pytest

from apps.accounts_rbac.demo_accounts import CLIENT_DEMO_EMAIL, ensure_client_demo_user
from apps.rfp_debate.client_session_list import COMPLETED_STATUSES, serialize_rfp_session_summary
from apps.rfp_debate.models import RFPStatus, RFPSubmission


@pytest.mark.django_db
def test_session_summary_completed(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        status=RFPStatus.PROPOSAL_RENDERED,
        source_document_text="Summit for Acme",
        active_ui_cards_json={
            "event_overview": {"company_name": "Acme Corp", "check_in_date": "2027-06-01"},
            "room_block": {"peak_rooms": 10},
            "live_quote": {"anchor_price": "15000"},
        },
        client_session_json={
            "transcript": [{"role": "user", "text": "Need 10 rooms", "at": "2026-01-01T00:00:00+00:00"}],
            "events": [],
        },
    )
    data = serialize_rfp_session_summary(rfp)
    assert data["completed"] is True
    assert data["proposal_card"]["company_name"] == "Acme Corp"
    assert "10 rooms" in data["last_snippet"] or "Need" in data["last_snippet"]


@pytest.mark.django_db
def test_client_demo_user():
    user = ensure_client_demo_user(reset_password=True)
    assert user.email == CLIENT_DEMO_EMAIL
    assert user.role == "CLIENT"
