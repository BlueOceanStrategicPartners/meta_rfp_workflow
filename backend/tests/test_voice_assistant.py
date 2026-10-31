import pytest


@pytest.mark.django_db
def test_voice_assistant_chat(api_client, settings):
    settings.USE_FIXTURE_DEBATE = True
    response = api_client.post(
        "/api/negotiation/voice-chat/",
        {"message": "We need the grand ballroom on the map"},
        format="json",
    )
    assert response.status_code == 200
    assert "reply" in response.json()


@pytest.mark.django_db
def test_voice_assistant_chat_stream(api_client, settings):
    settings.USE_FIXTURE_DEBATE = True
    response = api_client.post(
        "/api/negotiation/voice-chat/stream/",
        {"message": "We need the grand ballroom on the map"},
        format="json",
    )
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode()
    assert "event: status" in body
    assert "event: done" in body
    assert "reply" in body
