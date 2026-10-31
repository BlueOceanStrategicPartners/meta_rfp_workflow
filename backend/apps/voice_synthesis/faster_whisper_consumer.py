"""Browser PCM → faster-whisper via background worker."""
from __future__ import annotations

import json
import uuid

from django.conf import settings

from .local_pcm_consumer import LocalPCM_ASRConsumer
from .faster_whisper_worker import (
    ensure_worker_started,
    get_asr_worker,
    transcribe_pcm16_async,
    wait_until_asr_ready,
)


class FasterWhisperLocalConsumer(LocalPCM_ASRConsumer):
    worker_ensure = staticmethod(ensure_worker_started)
    worker_get = staticmethod(get_asr_worker)
    wait_ready = staticmethod(wait_until_asr_ready)
    transcribe_async = staticmethod(transcribe_pcm16_async)

    loading_message = "Loading faster-whisper (first run downloads ~500 MB for small.en)…"
    error_label = "faster-whisper"

    async def send_ready(self) -> None:
        await self.send(
            json.dumps(
                {
                    "type": "ready",
                    "sessionId": str(uuid.uuid4()),
                    "mode": "FASTER_WHISPER",
                    "engine": getattr(settings, "FASTER_WHISPER_MODEL", "small.en"),
                }
            )
        )
