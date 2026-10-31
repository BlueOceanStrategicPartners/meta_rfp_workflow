import pytest
from rest_framework.test import APIClient

from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_cards_snapshot_endpoint(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="I need three nights",
    )
    client = APIClient()
    response = client.get(f"/api/rfp/{rfp.pk}/cards/", HTTP_HOST="localhost")
    assert response.status_code == 200
    cards = response.json()["cards"]
    assert cards["event_overview"]["company_name"]
    assert cards["room_block"]["total_room_nights"] == 3
