import pytest

from apps.rfp_debate.card_identified import cards_have_identified_fields
from apps.rfp_debate.card_normalize import normalize_cards_for_ui
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_voice_only_create_no_placeholder_shell(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="Hi, how are you doing? Thank you.",
    )
    normalize_cards_for_ui(rfp, fill_placeholders=False)
    rfp.refresh_from_db()
    assert not cards_have_identified_fields(rfp.active_ui_cards_json or {})
    assert (rfp.client_session_json or {}).get("clarification_options") == []
