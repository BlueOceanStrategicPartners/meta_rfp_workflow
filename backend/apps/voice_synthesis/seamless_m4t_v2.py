"""SeamlessM4T v2 text-to-speech for the voice assistant (Meta Seamless Communication)."""
from __future__ import annotations

import asyncio
import io
import logging
import math
import struct
import wave
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_model: Any = None
_processor: Any = None


@dataclass(frozen=True)
class SynthesizedAudio:
    data: bytes
    content_type: str = "audio/wav"
    browser_fallback: bool = False


def _fixture_wav(text: str, sample_rate: int = 16_000) -> bytes:
    """Deterministic short WAV for tests/CI when GPU model is not loaded."""
    duration = min(3.0, 0.35 + len(text) * 0.018)
    n_frames = int(sample_rate * duration)
    freq = 440 + (len(text) % 8) * 40
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            t = i / sample_rate
            sample = int(22000 * math.sin(2 * math.pi * freq * t) * math.exp(-t * 0.35))
            wf.writeframes(struct.pack("<h", sample))
    return buffer.getvalue()


async def _edge_neural_mp3_async(text: str, voice: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()


def _edge_neural_mp3(text: str) -> bytes | None:
    """Natural neural speech while Seamless weights are not loaded (dev/demo)."""
    if not getattr(settings, "EDGE_NEURAL_TTS", True):
        return None
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return None

    voice = getattr(settings, "EDGE_NEURAL_VOICE", "en-US-AriaNeural")
    cleaned = text.strip()[:5000]
    if not cleaned:
        return None

    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_edge_neural_mp3_async(cleaned, voice))
        finally:
            loop.close()
    except Exception as exc:
        logger.warning("Edge neural TTS failed, falling back: %s", exc)
        return None


def _load_model() -> tuple[Any, Any]:
    global _model, _processor
    if _model is not None and _processor is not None:
        return _model, _processor
    from transformers import AutoProcessor, SeamlessM4Tv2Model

    model_id = settings.SEAMLESS_M4T_V2_MODEL
    _processor = AutoProcessor.from_pretrained(model_id)
    _model = SeamlessM4Tv2Model.from_pretrained(model_id)
    device = settings.SEAMLESS_M4T_DEVICE
    if device == "cuda":
        import torch

        if torch.cuda.is_available():
            _model = _model.to("cuda")
    _model.eval()
    return _model, _processor


def synthesize_speech(
    text: str,
    *,
    src_lang: str | None = None,
    tgt_lang: str | None = None,
) -> SynthesizedAudio:
    """
    Synthesize expressive speech with SeamlessM4T v2 (required TTS for voice assistant).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return SynthesizedAudio(_fixture_wav("."), browser_fallback=True)

    if settings.USE_SEAMLESS_FIXTURE:
        neural = _edge_neural_mp3(cleaned)
        if neural:
            return SynthesizedAudio(neural, content_type="audio/mpeg")
        return SynthesizedAudio(_fixture_wav(cleaned), browser_fallback=True)

    src = src_lang or settings.SEAMLESS_M4T_SRC_LANG
    tgt = tgt_lang or settings.SEAMLESS_M4T_TGT_LANG

    import torch

    model, processor = _load_model()
    inputs = processor(text=cleaned, src_lang=src, return_tensors="pt")
    if settings.SEAMLESS_M4T_DEVICE == "cuda" and torch.cuda.is_available():
        inputs = {k: v.to("cuda") if hasattr(v, "to") else v for k, v in inputs.items()}

    with torch.no_grad():
        output_tokens = model.generate(**inputs, tgt_lang=tgt, generate_speech=True)

    audio_array = processor.decode(output_tokens[0].cpu().numpy(), decode_audio=True)
    sample_rate = getattr(processor.model.config, "sampling_rate", 16_000)

    import soundfile as sf

    buffer = io.BytesIO()
    sf.write(buffer, audio_array, samplerate=sample_rate, format="WAV")
    return SynthesizedAudio(buffer.getvalue())
