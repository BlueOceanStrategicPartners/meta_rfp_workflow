"""Browser PCM → local OmniASR via dedicated inference worker."""
from __future__ import annotations

import json
import uuid

from django.conf import settings

from .local_pcm_consumer import LocalPCM_ASRConsumer
from .omniasr_worker import (
    ensure_worker_started,
    get_asr_worker,
    transcribe_pcm16_async,
    wait_until_asr_ready,
)


class OmniASRLocalConsumer(LocalPCM_ASRConsumer):
    worker_ensure = staticmethod(ensure_worker_started)
    worker_get = staticmethod(get_asr_worker)
    wait_ready = staticmethod(wait_until_asr_ready)
    transcribe_async = staticmethod(transcribe_pcm16_async)

    loading_message = "OmniASR worker loading model (first run may download ~650 MB)…"
    error_label = "OmniASR"

    async def send_ready(self) -> None:
        await self.send(
            json.dumps(
                {
                    "type": "ready",
                    "sessionId": str(uuid.uuid4()),
                    "mode": "OMNIASR_LOCAL",
                    "engine": getattr(
                        settings,
                        "OMNIASR_ONNX_MODEL",
                        "EmreAkgul/omniASR-CTC-300M-v2-ONNX",
                    ),
                }
            )
        )
