from apps.voice_synthesis.omniasr_worker import get_asr_worker


def test_worker_status_before_ready():
    worker = get_asr_worker()
    st = worker.status()
    assert "ready" in st
    assert "loading" in st
