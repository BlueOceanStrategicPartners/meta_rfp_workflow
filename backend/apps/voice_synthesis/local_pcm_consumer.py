"""Shared WebSocket PCM capture + endpointing for local ASR backends."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, ClassVar

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .omniasr_engine import pcm16_bytes_to_float32, rms_level

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_MS = 20
SPEECH_RMS = float(getattr(settings, "OMNIASR_SPEECH_RMS", 0.009))
SILENCE_END_MS = int(getattr(settings, "OMNIASR_SILENCE_END_MS", 1200))
PARTIAL_INTERVAL_MS = int(getattr(settings, "OMNIASR_PARTIAL_MS", 0))
MIN_UTTERANCE_MS = int(getattr(settings, "OMNIASR_MIN_UTTERANCE_MS", 400))
MAX_UTTERANCE_MS = int(getattr(settings, "OMNIASR_MAX_UTTERANCE_MS", 30000))


class LocalPCM_ASRConsumer(AsyncWebsocketConsumer):
    loading_message: ClassVar[str] = "Loading speech model…"
    error_label: ClassVar[str] = "Local ASR"

    worker_ensure: ClassVar[Callable[[], None]]
    worker_get: ClassVar[Callable[[], Any]]
    wait_ready: ClassVar[Callable[..., Any]]
    transcribe_async: ClassVar[Callable[[bytes], Any]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._decode_lock = asyncio.Lock()
        self._utterance = bytearray()
        self._in_speech = False
        self._silence_ms = 0
        self._speech_ms = 0
        self._last_partial_ms = 0
        self._turn_id = 0
        self._closed = False

    async def connect(self):
        self._closed = False
        await self.accept()
        self.worker_ensure()

        worker = self.worker_get()
        st = worker.status()
        if not st["ready"]:
            await self.send(
                json.dumps({"type": "loading", "message": self.loading_message}),
            )

        ok, err = await self.wait_ready(timeout=600.0)
        if self._closed:
            return
        if not ok:
            await self.send(
                json.dumps(
                    {
                        "type": "error",
                        "message": err or f"{self.error_label} failed to start.",
                    }
                )
            )
            await self.close(code=1011)
            return

        await self.send_ready()

    async def send_ready(self) -> None:
        raise NotImplementedError

    async def receive(self, text_data=None, bytes_data=None):
        if self._closed:
            return
        if text_data:
            try:
                payload = json.loads(text_data)
            except json.JSONDecodeError:
                return
            if payload.get("type") == "endStream":
                await self._finalize_turn(force=True)
            elif payload.get("type") == "pauseCapture":
                self._reset_turn()
            return
        if bytes_data:
            await self._ingest_pcm(bytes_data)

    async def _ingest_pcm(self, chunk: bytes) -> None:
        if self._closed:
            return
        frame_samples = len(chunk) // 2
        frame_ms = int((frame_samples / SAMPLE_RATE) * 1000) if frame_samples else FRAME_MS
        level = rms_level(pcm16_bytes_to_float32(chunk))

        if level >= SPEECH_RMS:
            if not self._in_speech:
                self._in_speech = True
                self._silence_ms = 0
                self._speech_ms = 0
                self._last_partial_ms = 0
                self._utterance.clear()
                await self.send(json.dumps({"type": "speechStart", "turnId": self._turn_id}))
            self._utterance.extend(chunk)
            self._speech_ms += frame_ms
            self._silence_ms = 0
            if (
                PARTIAL_INTERVAL_MS > 0
                and self._speech_ms >= MIN_UTTERANCE_MS
                and self._speech_ms - self._last_partial_ms >= PARTIAL_INTERVAL_MS
            ):
                self._last_partial_ms = self._speech_ms
                await self._emit_partial()
            if self._speech_ms >= MAX_UTTERANCE_MS:
                await self._finalize_turn(force=True)
            return

        if not self._in_speech:
            return

        self._silence_ms += frame_ms
        if level >= SPEECH_RMS * 0.45:
            self._utterance.extend(chunk)
            self._silence_ms = max(0, self._silence_ms - frame_ms)
        if self._silence_ms >= SILENCE_END_MS:
            await self._finalize_turn(force=False)

    async def _emit_partial(self) -> None:
        if self._closed:
            return
        text = await self._decode_utterance()
        if not text or self._closed:
            return
        await self.send(json.dumps({"type": "transcript", "text": text, "final": False}))

    async def _finalize_turn(self, *, force: bool) -> None:
        if self._closed:
            return
        if not self._in_speech and not force:
            return
        if self._speech_ms < MIN_UTTERANCE_MS and not force:
            self._reset_turn()
            return
        text = await self._decode_utterance()
        self._turn_id += 1
        self._reset_turn()
        if text and not self._closed:
            await self.send(
                json.dumps(
                    {"type": "turnComplete", "text": text, "turnId": self._turn_id},
                )
            )

    async def _decode_utterance(self) -> str:
        if self._closed:
            return ""
        pcm = bytes(self._utterance)
        if len(pcm) < (SAMPLE_RATE // 5) * 2:
            return ""
        async with self._decode_lock:
            if self._closed:
                return ""
            try:
                return await self.transcribe_async(pcm)
            except Exception as exc:
                logger.warning("%s decode error: %s", self.error_label, exc)
                if not self._closed:
                    await self.send(json.dumps({"type": "error", "message": str(exc)}))
                return ""

    def _reset_turn(self) -> None:
        self._in_speech = False
        self._silence_ms = 0
        self._speech_ms = 0
        self._last_partial_ms = 0
        self._utterance.clear()

    async def disconnect(self, close_code):
        self._closed = True
