import pytest
from rest_framework.test import APIClient

from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_archive_session_endpoint(client_user):
    rfp = RFPSubmission.objects.create(client=client_user, client_session_json={})
    api = APIClient()
    api.force_authenticate(user=client_user)

    res = api.post(f"/api/rfp/{rfp.pk}/archive/", {"archived": True}, format="json", HTTP_HOST="localhost")
    assert res.status_code == 200
    assert res.json()["archived"] is True

    rfp.refresh_from_db()
    assert rfp.client_session_json.get("archived") is True

    res2 = api.post(f"/api/rfp/{rfp.pk}/archive/", {"archived": False}, format="json", HTTP_HOST="localhost")
    assert res2.status_code == 200
    assert res2.json()["archived"] is False


@pytest.mark.django_db
def test_archive_session_via_patch_detail(client_user):
    rfp = RFPSubmission.objects.create(client=client_user, client_session_json={})
    api = APIClient()
    api.force_authenticate(user=client_user)

    res = api.patch(f"/api/rfp/{rfp.pk}/", {"archived": True}, format="json", HTTP_HOST="localhost")
    assert res.status_code == 200
    assert res.json()["archived"] is True


@pytest.mark.django_db
def test_archive_session_via_sessions_post(client_user):
    rfp = RFPSubmission.objects.create(client=client_user, client_session_json={})
    api = APIClient()
    api.force_authenticate(user=client_user)

    res = api.post(
        "/api/rfp/sessions/",
        {"session_id": str(rfp.pk), "archived": True},
        format="json",
        HTTP_HOST="localhost",
    )
    assert res.status_code == 200
    assert res.json()["archived"] is True
