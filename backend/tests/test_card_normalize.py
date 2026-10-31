import pytest

from apps.rfp_debate.card_normalize import normalize_cards_for_ui
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_normalize_cards_from_voice_three_nights(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="So, I want three nights",
    )
    normalize_cards_for_ui(rfp)
    rfp.refresh_from_db()
    overview = rfp.active_ui_cards_json["event_overview"]
    assert overview["company_name"] == "Your organization"
    assert rfp.active_ui_cards_json["room_block"]["total_room_nights"] == 3
