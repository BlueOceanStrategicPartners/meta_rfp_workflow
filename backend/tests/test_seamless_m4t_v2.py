import pytest


@pytest.mark.django_db
def test_seamless_m4t_v2_synthesize_returns_wav(api_client, settings):
    settings.USE_SEAMLESS_FIXTURE = True
    settings.EDGE_NEURAL_TTS = False
    response = api_client.post(
        "/api/voice/seamless-m4t-v2/synthesize/",
        {"text": "Your ballroom is available for two hundred fifty guests."},
        format="json",
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "audio/wav"
    assert response["X-Voice-Engine"] == "SeamlessM4T-v2"
    assert response.content[:4] == b"RIFF"


def test_seamless_m4t_v2_status(api_client):
    response = api_client.get("/api/voice/seamless-m4t-v2/status/")
    assert response.status_code == 200
    assert response.json()["engine"] == "SeamlessM4T-v2"
    assert response.json()["required"] is True
