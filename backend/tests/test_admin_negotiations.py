import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.admin_command_center.models import AdminAuditEvent
from apps.rfp_debate.models import RFPStatus


def _listen(rfp_id):
    """Join the client's RFP group so we can see what gets broadcast to the browser."""
    layer = get_channel_layer()
    channel = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(f"rfp_{rfp_id}", channel)
    return layer, channel


def _next(layer, channel):
    return async_to_sync(layer.receive)(channel)


@pytest.mark.django_db
def test_list_shows_active_negotiations(admin_client, seeded_rfp):
    rows = admin_client.get("/api/admin-center/negotiations/").json()
    assert rows[0]["id"] == str(seeded_rfp.id)
    assert rows[0]["taken_over"] is False
    assert rows[0]["latest_quote"]["anchor"]


@pytest.mark.django_db
def test_takeover_message_and_release(admin_client, admin_user, seeded_rfp):
    layer, channel = _listen(seeded_rfp.id)
    url = f"/api/admin-center/negotiations/{seeded_rfp.id}"

    assert admin_client.post(f"{url}/message/", {"text": "hi"}, format="json").status_code == 409

    res = admin_client.post(f"{url}/takeover/")
    assert res.status_code == 200
    seeded_rfp.refresh_from_db()
    assert seeded_rfp.status == RFPStatus.ESCALATED
    assert "joining" in _next(layer, channel)["payload"]["text"]
    assert admin_client.post(f"{url}/takeover/").status_code == 409

    row = admin_client.get("/api/admin-center/negotiations/").json()[0]
    assert row["taken_over"] is True and row["taken_over_by"] == admin_user.email

    msg = admin_client.post(f"{url}/message/", {"text": "We can include AV at no charge."}, format="json")
    assert msg.status_code == 200
    spoken = _next(layer, channel)
    assert spoken["message_type"] == "agent_utterance"
    assert spoken["payload"]["text"] == "We can include AV at no charge."

    assert admin_client.post(f"{url}/release/").status_code == 200
    seeded_rfp.refresh_from_db()
    assert seeded_rfp.status == RFPStatus.NEGOTIATING  # restored, not hard-coded
    actions = list(AdminAuditEvent.objects.values_list("action", flat=True))
    assert {"negotiation.takeover", "negotiation.message", "negotiation.release"} <= set(actions)


@pytest.mark.django_db
def test_assistant_is_silent_during_takeover(api_client, admin_client, seeded_rfp):
    admin_client.post(f"/api/admin-center/negotiations/{seeded_rfp.id}/takeover/")
    api_client.force_authenticate(user=None)
    res = api_client.post(
        "/api/negotiation/voice-chat/", {"message": "Can you do a discount?", "rfp_id": str(seeded_rfp.id)}, format="json"
    )
    assert res.status_code == 200
    assert res.json()["human_takeover"] is True

    stream = api_client.post(
        "/api/negotiation/voice-chat/stream/", {"message": "hello?", "rfp_id": str(seeded_rfp.id)}, format="json"
    )
    body = b"".join(stream.streaming_content).decode()
    assert "event: done" in body and "human_takeover" in body


@pytest.mark.django_db
def test_cannot_take_over_a_booked_request(admin_client, seeded_rfp):
    seeded_rfp.status = RFPStatus.BOOKED
    seeded_rfp.save(update_fields=["status"])
    res = admin_client.post(f"/api/admin-center/negotiations/{seeded_rfp.id}/takeover/")
    assert res.status_code == 409
    assert "booked" in res.json()["detail"]


@pytest.mark.django_db
def test_release_without_takeover_and_message_limits(admin_client, seeded_rfp):
    url = f"/api/admin-center/negotiations/{seeded_rfp.id}"
    assert admin_client.post(f"{url}/release/").status_code == 409
    admin_client.post(f"{url}/takeover/")
    assert admin_client.post(f"{url}/message/", {"text": "   "}, format="json").status_code == 400
    assert admin_client.post(f"{url}/message/", {"text": "x" * 501}, format="json").status_code == 400
