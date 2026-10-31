from apps.voice_synthesis.omniasr_engine import pcm16_bytes_to_float32, rms_level, trim_pcm_silence


def test_rms_silence():
    silent = pcm16_bytes_to_float32(b"\x00\x00" * 320)
    assert rms_level(silent) == 0.0


def test_rms_detects_signal():
    import numpy as np

    wave = (np.sin(np.linspace(0, 8, 3200)) * 16000).astype(np.int16)
    assert rms_level(pcm16_bytes_to_float32(wave.tobytes())) > 0.05


def test_trim_keeps_speech_core():
    import numpy as np

    sr = 16000
    silence = np.zeros(sr // 2, dtype=np.int16)
    tone = (np.sin(np.linspace(0, 40, sr)) * 12000).astype(np.int16)
    pcm = np.concatenate([silence, tone, silence]).tobytes()
    trimmed = trim_pcm_silence(pcm, sample_rate=sr)
    assert len(trimmed) < len(pcm)
    wave = pcm16_bytes_to_float32(trimmed)
    assert wave.size > sr // 3
