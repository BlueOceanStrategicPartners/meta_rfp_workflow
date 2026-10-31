"""Proxy browser PCM to Meta Muse Voice Transcribe realtime ASR."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)

META_ASR_URI = "wss://api.meta.ai/v1/asr/realtime"


def meta_event_to_client(event: dict) -> dict | None:
    """Map a Meta ASR server event to a browser-facing JSON message."""
    event_type = event.get("type")
    if event_type == "error":
        return {
            "type": "error",
            "message": event.get("message", "Meta ASR error"),
        }
    if event_type == "transcript":
        payload: dict = {
            "type": "transcript",
            "text": event.get("transcript", ""),
            "final": bool(event.get("final")),
        }
        if "audioProcessedMs" in event:
            payload["audioProcessedMs"] = event["audioProcessedMs"]
        return payload
    if event_type == "speechComplete":
        return {
            "type": "turnComplete",
            "text": event.get("transcript", ""),
            "turnId": event.get("turnId"),
        }
    if event_type == "speechStart":
        return {
            "type": "speechStart",
            "turnId": event.get("turnId"),
            "audioProcessedMs": event.get("audioProcessedMs"),
        }
    if event_type == "speechEnd":
        return {
            "type": "speechEnd",
            "turnId": event.get("turnId"),
            "audioProcessedMs": event.get("audioProcessedMs"),
        }
    return None


class MuseASRProxyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        api_key = settings.META_MODEL_API_KEY
        if not api_key:
            await self.send(
                json.dumps(
                    {
                        "type": "error",
                        "message": "META_MODEL_API_KEY is not configured on the server.",
                    }
                )
            )
            await self.close(code=4401)
            return

        self.meta_ws = None
        self._relay_task: asyncio.Task | None = None
        session_id = str(uuid.uuid4())

        try:
            uri = f"{META_ASR_URI}?sessionId={session_id}"
            self.meta_ws = await websockets.connect(uri, open_timeout=30)
            model = getattr(settings, "MUSE_VOICE_TRANSCRIBE_MODEL", "muse-voice-transcribe-1.0")
            asr_mode = getattr(settings, "MUSE_ASR_MODE", "ENDPOINTING")
            handshake = {
                "authorization": {"accessToken": f"Bearer {api_key}"},
                "audioEncoding": "PCM_16KHZ",
                "model": model,
                "mode": asr_mode,
            }
            await self.meta_ws.send(json.dumps(handshake))
            raw_ack = await asyncio.wait_for(self.meta_ws.recv(), timeout=15)
            if isinstance(raw_ack, bytes):
                raise RuntimeError("Unexpected binary handshake response from Meta ASR")
            ack = json.loads(raw_ack)
            if "sessionId" not in ack:
                raise RuntimeError(f"Meta ASR handshake failed: {ack}")

            await self.send(
                json.dumps(
                    {
                        "type": "ready",
                        "sessionId": ack["sessionId"],
                        "mode": asr_mode,
                    }
                )
            )
            self._relay_task = asyncio.create_task(self._relay_meta_to_client())
        except Exception as exc:
            logger.exception("ASR proxy connect failed")
            await self.send(json.dumps({"type": "error", "message": str(exc)}))
            await self._close_meta()
            await self.close(code=1011)

    async def _relay_meta_to_client(self) -> None:
        assert self.meta_ws is not None
        try:
            async for message in self.meta_ws:
                if isinstance(message, bytes):
                    continue
                event = json.loads(message)
                client_msg = meta_event_to_client(event)
                if client_msg:
                    await self.send(json.dumps(client_msg))
        except asyncio.CancelledError:
            raise
        except websockets.exceptions.ConnectionClosed as exc:
            logger.info("Meta ASR closed code=%s reason=%s", exc.code, exc.reason)
            msg = f"Meta ASR closed ({exc.code}): {exc.reason or 'connection closed'}"
            await self.send(json.dumps({"type": "error", "message": msg}))
        except Exception as exc:
            logger.warning("ASR relay ended: %s", exc)
            await self.send(json.dumps({"type": "error", "message": str(exc)}))

    async def receive(self, text_data=None, bytes_data=None):
        if not self.meta_ws:
            return
        try:
            if bytes_data is not None:
                await self.meta_ws.send(bytes_data)
            elif text_data:
                payload = json.loads(text_data)
                if payload.get("type") == "endStream":
                    await self.meta_ws.send(text_data)
        except Exception as exc:
            await self.send(json.dumps({"type": "error", "message": str(exc)}))

    async def _close_meta(self) -> None:
        if self._relay_task:
            self._relay_task.cancel()
            try:
                await self._relay_task
            except asyncio.CancelledError:
                pass
            self._relay_task = None
        if self.meta_ws:
            try:
                await self.meta_ws.close()
            except Exception:
                pass
            self.meta_ws = None

    async def disconnect(self, close_code):
        await self._close_meta()
