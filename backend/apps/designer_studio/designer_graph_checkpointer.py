"""LangGraph checkpoint savers for Design Studio (SQLite dev / in-memory tests)."""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from django.conf import settings
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from .designer_graph_state import DesignerGraphConfigurable

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_saver: BaseCheckpointSaver | None = None
_conn: sqlite3.Connection | None = None


def designer_checkpoint_db_path() -> Path:
    base = Path(settings.BASE_DIR)
    return base / "designer_langgraph_checkpoints.sqlite"


def get_designer_checkpointer() -> BaseCheckpointSaver:
    """Process-wide checkpointer (SQLite file or in-memory for tests)."""
    global _saver, _conn
    with _lock:
        if _saver is not None:
            return _saver

        backend = getattr(settings, "DESIGNER_LANGGRAPH_CHECKPOINT_BACKEND", "sqlite").strip().lower()
        if backend == "memory":
            from langgraph.checkpoint.memory import InMemorySaver

            _saver = InMemorySaver()
            logger.info("Designer LangGraph checkpointer: InMemorySaver")
            return _saver

        from langgraph.checkpoint.sqlite import SqliteSaver

        path = designer_checkpoint_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _saver = SqliteSaver(_conn)
        _saver.setup()
        logger.info("Designer LangGraph checkpointer: SqliteSaver path=%s", path)
        return _saver


def build_runnable_config(
    *,
    thread_id: str,
    checkpoint_id: str | None = None,
) -> RunnableConfig:
    """Checkpoint-safe configurable (no callables — use designer_graph_callbacks ContextVar)."""
    configurable: DesignerGraphConfigurable = {
        "thread_id": thread_id,
    }
    if checkpoint_id:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": dict(configurable)}


def reset_designer_graph_runtime_for_tests() -> None:
    """Clear singleton graph/checkpointer (unit tests only)."""
    global _saver, _conn
    with _lock:
        _saver = None
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None
    from . import designer_langgraph as lg

    lg.reset_compiled_designer_graph_for_tests()


def read_latest_checkpoint_id(graph: Any, config: RunnableConfig) -> str | None:
    """Best-effort checkpoint id after invoke (for SSE / debug)."""
    try:
        snap = graph.get_state(config)
    except Exception:
        return None
    if not snap or not snap.config:
        return None
    cfg = snap.config.get("configurable") or {}
    cid = cfg.get("checkpoint_id")
    return str(cid) if cid else None
