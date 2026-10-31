"""Local Meta omniASR_CTC_300M_v2 — PyTorch+transformers or ONNX (fast-omniasr, no torch).

Use OMNIASR_RUNTIME=onnx when llama.cpp already owns CUDA via its own runtime;
ONNX Runtime uses a separate allocator (~1.4 GiB FP16 on GPU for 300M).
"""
from __future__ import annotations

import logging
import re
import threading
from typing import TYPE_CHECKING, Any

import numpy as np
from django.conf import settings

if TYPE_CHECKING:
    from transformers import AutoProcessor, Wav2Vec2ForCTC

logger = logging.getLogger(__name__)

_load_lock = threading.Lock()
_torch_runtime: tuple["AutoProcessor", "Wav2Vec2ForCTC", str] | None = None
_onnx_runtime: Any | None = None
_loaded_model_key: str | None = None

DEFAULT_HF_MODEL = "aadel4/omniASR-CTC-300M-v2"
DEFAULT_ONNX_MODEL = "EmreAkgul/omniASR-CTC-300M-v2-ONNX"
ACCURATE_HF_MODEL = "aadel4/omniASR-CTC-1B-v2"
ACCURATE_ONNX_MODEL = "EmreAkgul/omniASR-CTC-1B-v2-ONNX"


def runtime_mode() -> str:
    mode = getattr(settings, "OMNIASR_RUNTIME", "onnx").lower()
    if mode == "onnx":
        try:
            import fast_omniasr  # noqa: F401
        except ImportError:
            logger.warning("fast-omniasr not installed — falling back to torch runtime")
            return "torch"
    return mode if mode in {"onnx", "torch"} else "onnx"


def _import_torch():
    try:
        import torch
    except OSError as exc:
        raise RuntimeError(
            "PyTorch failed to load (often a broken CUDA install). "
            "Prefer OMNIASR_RUNTIME=onnx with pip install \"fast-omniasr[onnx,hub,cuda]\", "
            "or reinstall CPU torch: pip install torch --index-url https://download.pytorch.org/whl/cpu"
        ) from exc
    return torch


def resolve_device() -> str:
    requested = getattr(settings, "OMNIASR_DEVICE", "cpu").lower()
    if requested != "cuda":
        return "cpu"
    if runtime_mode() == "onnx":
        try:
            import onnxruntime as ort

            if "CUDAExecutionProvider" in ort.get_available_providers():
                return "cuda"
        except ImportError:
            pass
        logger.warning("OMNIASR_DEVICE=cuda but ONNX CUDA EP unavailable — using CPU")
        return "cpu"
    torch = _import_torch()
    if torch.cuda.is_available():
        return "cuda"
    logger.warning("OMNIASR_DEVICE=cuda but CUDA unavailable — using CPU")
    return "cpu"


def _load_onnx_model():
    global _onnx_runtime
    from fast_omniasr import OmniASR

    model_id = getattr(settings, "OMNIASR_ONNX_MODEL", DEFAULT_ONNX_MODEL)
    device = resolve_device()
    default_precision = "fp16" if device == "cuda" else "fp32"
    precision = getattr(settings, "OMNIASR_ONNX_PRECISION", default_precision)
    # Honor explicit env; fp16 on CPU is valid when weights are already cached locally.
    logger.info("Loading OmniASR ONNX %s device=%s precision=%s", model_id, device, precision)
    threads = int(getattr(settings, "OMNIASR_ONNX_THREADS", 4))
    _onnx_runtime = OmniASR.from_pretrained(
        model_id,
        backend="onnx",
        device=device,
        precision=precision,
        threads=threads,
    )
    return _onnx_runtime


def _current_model_key() -> str:
    if runtime_mode() == "onnx":
        return f"onnx:{getattr(settings, 'OMNIASR_ONNX_MODEL', DEFAULT_ONNX_MODEL)}"
    return f"torch:{getattr(settings, 'OMNIASR_MODEL_HF', DEFAULT_HF_MODEL)}"


def is_model_loaded() -> bool:
    if runtime_mode() == "onnx":
        return _onnx_runtime is not None
    return _torch_runtime is not None


def load_omniasr_model():
    global _torch_runtime, _onnx_runtime, _loaded_model_key
    key = _current_model_key()
    with _load_lock:
        if _loaded_model_key == key:
            if runtime_mode() == "onnx" and _onnx_runtime is not None:
                return _onnx_runtime
            if runtime_mode() == "torch" and _torch_runtime is not None:
                return _torch_runtime
        _onnx_runtime = None
        _torch_runtime = None
        if runtime_mode() == "onnx":
            model = _load_onnx_model()
            _loaded_model_key = key
            return model
        _import_torch()
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        model_id = getattr(settings, "OMNIASR_MODEL_HF", DEFAULT_HF_MODEL)
        device = resolve_device()
        logger.info("Loading OmniASR torch %s on %s", model_id, device)
        processor = AutoProcessor.from_pretrained(model_id)
        model = Wav2Vec2ForCTC.from_pretrained(model_id, low_cpu_mem_usage=True)
        model.to(device)
        model.eval()
        _torch_runtime = (processor, model, device)
        _loaded_model_key = key
        return _torch_runtime


def pcm16_bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
    if not pcm_bytes:
        return np.array([], dtype=np.float32)
    pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
    return (pcm.astype(np.float32) / 32768.0).clip(-1.0, 1.0)


def rms_level(waveform: np.ndarray) -> float:
    if waveform.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(waveform))))


def normalize_transcript(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def trim_pcm_silence(
    pcm_bytes: bytes,
    *,
    sample_rate: int = 16000,
    frame_ms: int = 20,
    rms_threshold: float = 0.006,
    pad_ms: int = 120,
) -> bytes:
    """Drop leading/trailing silence; keep short padding for CTC context."""
    waveform = pcm16_bytes_to_float32(pcm_bytes)
    if waveform.size == 0:
        return pcm_bytes
    frame = max(1, int(sample_rate * frame_ms / 1000))
    n_frames = max(1, waveform.size // frame)
    active = []
    for i in range(n_frames):
        chunk = waveform[i * frame : (i + 1) * frame]
        active.append(rms_level(chunk) >= rms_threshold)
    if not any(active):
        return pcm_bytes
    start = next(i for i, on in enumerate(active) if on)
    end = len(active) - 1 - next(i for i, on in enumerate(reversed(active)) if on)
    pad = int(sample_rate * pad_ms / 1000)
    lo = max(0, start * frame - pad)
    hi = min(waveform.size, (end + 1) * frame + pad)
    trimmed = waveform[lo:hi]
    pcm = np.clip(trimmed * 32768.0, -32768, 32767).astype(np.int16)
    return pcm.tobytes()


def _transcribe_onnx(waveform: np.ndarray, sample_rate: int) -> str:
    model = load_omniasr_model()
    result = model.transcribe_numpy(waveform, sample_rate)
    text = getattr(result, "text", result)
    return normalize_transcript(str(text))


def _transcribe_torch(pcm_bytes: bytes, sample_rate: int) -> str:
    waveform = pcm16_bytes_to_float32(pcm_bytes)
    torch = _import_torch()
    processor, model, device = load_omniasr_model()
    inputs = processor(waveform, sampling_rate=sample_rate, return_tensors="pt", padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.inference_mode():
        logits = model(**inputs).logits
    pred_ids = torch.argmax(logits, dim=-1)
    text = processor.batch_decode(pred_ids)[0]
    return normalize_transcript(text)


def transcribe_pcm16(pcm_bytes: bytes, *, sample_rate: int = 16000) -> str:
    pcm_bytes = trim_pcm_silence(pcm_bytes, sample_rate=sample_rate)
    waveform = pcm16_bytes_to_float32(pcm_bytes)
    if waveform.size < sample_rate // 5:
        return ""
    if runtime_mode() == "onnx":
        return _transcribe_onnx(waveform, sample_rate)
    return _transcribe_torch(pcm_bytes, sample_rate)
