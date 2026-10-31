"""Dedicated OmniASR inference worker — model load + decode off the ASGI event loop."""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _InferenceJob:
    pcm: bytes
    future: Future[str]


class OmniASRInferenceWorker:
    """Single background thread: load model once, serialize all transcribe calls."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._load_error: str | None = None
        self._loading = False
        self._queue: queue.Queue[_InferenceJob | None] = queue.Queue()
        self._thread = threading.Thread(
            target=self._worker_main,
            name="omniasr-inference",
            daemon=True,
        )
        self._start_lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                return
            self._started = True
            self._loading = True
            self._thread.start()
            logger.info("OmniASR inference worker thread started")

    def status(self) -> dict[str, Any]:
        from .omniasr_engine import is_model_loaded

        if self._load_error:
            return {"ready": False, "loading": False, "error": self._load_error}
        if self._ready.is_set() or is_model_loaded():
            return {"ready": True, "loading": False}
        return {"ready": False, "loading": self._loading, "error": None}

    def wait_ready(self, timeout: float | None = None) -> tuple[bool, str | None]:
        self.start()
        if not self._ready.wait(timeout=timeout):
            return False, "OmniASR load timed out — check backend logs and disk space."
        if self._load_error:
            return False, self._load_error
        return True, None

    def submit_transcribe(self, pcm: bytes) -> Future[str]:
        self.start()
        if self._load_error:
            fut: Future[str] = Future()
            fut.set_exception(RuntimeError(self._load_error))
            return fut
        if not self._ready.is_set():
            fut = Future()
            fut.set_exception(RuntimeError("OmniASR worker not ready"))
            return fut
        fut = Future()
        self._queue.put(_InferenceJob(pcm=pcm, future=fut))
        return fut

    def _worker_main(self) -> None:
        try:
            from .omniasr_engine import is_model_loaded, load_omniasr_model

            if is_model_loaded():
                logger.info("OmniASR worker reusing loaded model")
            else:
                logger.info("OmniASR worker loading model (once per process)…")
                load_omniasr_model()
            logger.info("OmniASR worker model ready")
        except Exception as exc:
            logger.exception("OmniASR worker load failed")
            self._load_error = str(exc)
            self._loading = False
            self._ready.set()
            return

        self._loading = False
        self._ready.set()

        from .omniasr_engine import transcribe_pcm16

        while True:
            job = self._queue.get()
            if job is None:
                break
            try:
                text = transcribe_pcm16(job.pcm)
                job.future.set_result(text)
            except Exception as exc:
                job.future.set_exception(exc)
            finally:
                self._queue.task_done()


_worker: OmniASRInferenceWorker | None = None
_worker_lock = threading.Lock()


def get_asr_worker() -> OmniASRInferenceWorker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = OmniASRInferenceWorker()
        return _worker


def ensure_worker_started() -> None:
    get_asr_worker().start()


async def wait_until_asr_ready(timeout: float = 600.0) -> tuple[bool, str | None]:
    worker = get_asr_worker()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: worker.wait_ready(timeout=timeout))


async def transcribe_pcm16_async(pcm: bytes) -> str:
    worker = get_asr_worker()
    loop = asyncio.get_running_loop()
    future = worker.submit_transcribe(pcm)
    return await asyncio.wrap_future(future)
