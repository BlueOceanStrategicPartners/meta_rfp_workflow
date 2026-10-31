from apps.voice_synthesis.asr_consumer import meta_event_to_client


def test_meta_event_turn_complete():
    out = meta_event_to_client(
        {
            "type": "speechComplete",
            "turnId": 1,
            "transcript": "How is the weather?",
            "audioProcessedMs": 3600,
        }
    )
    assert out == {
        "type": "turnComplete",
        "text": "How is the weather?",
        "turnId": 1,
    }


def test_meta_event_transcript_partial():
    out = meta_event_to_client(
        {
            "type": "transcript",
            "transcript": "hello there",
            "final": False,
            "audioProcessedMs": 1200,
        }
    )
    assert out["type"] == "transcript"
    assert out["text"] == "hello there"
    assert out["final"] is False
    assert out["audioProcessedMs"] == 1200


def test_meta_event_speech_start_ignored_returns_payload():
    out = meta_event_to_client({"type": "speechStart", "turnId": 2, "audioProcessedMs": 100})
    assert out["type"] == "speechStart"
    assert out["turnId"] == 2
