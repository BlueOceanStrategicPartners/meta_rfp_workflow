"""Request-scoped SSE callbacks for LangGraph nodes (not stored in checkpoints)."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_stream_callbacks: ContextVar[dict[str, Any] | None] = ContextVar(
    "designer_graph_stream_callbacks", default=None
)


def push_stream_callbacks(callbacks: dict[str, Any]):
    return _stream_callbacks.set(dict(callbacks))


def pop_stream_callbacks(token) -> None:
    _stream_callbacks.reset(token)


def get_stream_callbacks() -> dict[str, Any]:
    return dict(_stream_callbacks.get() or {})
