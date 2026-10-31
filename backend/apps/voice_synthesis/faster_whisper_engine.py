"""Local ASR via faster-whisper (CTranslate2) — small download, strong English accuracy."""
from __future__ import annotations

import logging
import threading
from typing import Any

from django.conf import settings

from .omniasr_engine import normalize_transcript, pcm16_bytes_to_float32, trim_pcm_silence

logger = logging.getLogger(__name__)

_model: Any | None = None
_load_lock = threading.Lock()


def load_whisper_model():
    global _model
    with _load_lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel

        model_size = getattr(settings, "FASTER_WHISPER_MODEL", "small.en")
        device = getattr(settings, "FASTER_WHISPER_DEVICE", "cpu")
        compute_type = getattr(settings, "FASTER_WHISPER_COMPUTE_TYPE", "int8")
        logger.info(
            "Loading faster-whisper %s device=%s compute_type=%s",
            model_size,
            device,
            compute_type,
        )
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
        return _model


def is_model_loaded() -> bool:
    return _model is not None


def transcribe_pcm16(pcm_bytes: bytes, *, sample_rate: int = 16000) -> str:
    pcm_bytes = trim_pcm_silence(pcm_bytes, sample_rate=sample_rate)
    waveform = pcm16_bytes_to_float32(pcm_bytes)
    if waveform.size < sample_rate // 5:
        return ""

    model = load_whisper_model()
    language = getattr(settings, "FASTER_WHISPER_LANGUAGE", "en") or None
    segments, _info = model.transcribe(
        waveform,
        language=language,
        task="transcribe",
        vad_filter=True,
        condition_on_previous_text=False,
    )
    parts = [segment.text.strip() for segment in segments if segment.text.strip()]
    return normalize_transcript(" ".join(parts))
