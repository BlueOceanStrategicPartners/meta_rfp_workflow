from django.urls import re_path

from django.conf import settings

from .asr_consumer import MuseASRProxyConsumer
from .faster_whisper_consumer import FasterWhisperLocalConsumer
from .omniasr_consumer import OmniASRLocalConsumer


def _asr_consumer():
    backend = getattr(settings, "ASR_BACKEND", "omniasr").lower()
    if backend == "muse":
        return MuseASRProxyConsumer
    if backend in {"faster_whisper", "whisper", "fast_whisper"}:
        return FasterWhisperLocalConsumer
    return OmniASRLocalConsumer


websocket_urlpatterns = [
    re_path(r"ws/asr/$", _asr_consumer().as_asgi()),
]
