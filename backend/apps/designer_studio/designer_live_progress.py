"""In-memory live progress for design agent runs (poll fallback when SSE buffers)."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_by_user: dict[str, dict[str, Any]] = {}
_cancel_requested: dict[str, bool] = {}

STALE_ACTIVE_SECONDS = 600.0
GHOST_ACTIVE_SECONDS = 45.0


def _user_key(user_id: Any) -> str:
    return str(user_id)


def _snapshot_has_work(cur: dict[str, Any]) -> bool:
    if cur.get("agent_todos") or cur.get("work_plan") or cur.get("tool_steps"):
        return True
    preview = cur.get("preview")
    if isinstance(preview, dict):
        if (preview.get("html_markup") or "").strip():
            return True
        if (preview.get("css_stylesheet") or "").strip():
            return True
    return False


def _coerce_inactive_if_ghost(cur: dict[str, Any], *, now: float | None = None) -> bool:
    """Clear active when flag is set but no work signals (prevents frontend ghost busy)."""
    now = now if now is not None else time.time()
    updated = float(cur.get("updated_at") or 0)
    if not cur.get("active"):
        return False
    age = (now - updated) if updated else GHOST_ACTIVE_SECONDS + 1.0
    if age > STALE_ACTIVE_SECONDS:
        cur["active"] = False
        cur["updated_at"] = now
        logger.info("designer live progress: cleared stale active (age=%.0fs)", age)
        return True
    if not _snapshot_has_work(cur) and age > GHOST_ACTIVE_SECONDS:
        cur["active"] = False
        cur["updated_at"] = now
        logger.info("designer live progress: cleared ghost active (no work, age=%.0fs)", age)
        return True
    return False


def begin_live_progress(*, user_id: Any) -> None:
    key = _user_key(user_id)
    with _lock:
        _cancel_requested.pop(key, None)
        _by_user[key] = {
            "active": True,
            "updated_at": time.time(),
            "agent_todos": [],
            "work_plan": [],
            "tool_steps": [],
        }


def request_designer_agent_cancel(*, user_id: Any) -> None:
    """User cleared chat or closed the stream — stop tool loop / map stage for this designer."""
    key = _user_key(user_id)
    with _lock:
        _cancel_requested[key] = True
        cur = _by_user.get(key)
        if cur:
            cur["active"] = False
            cur["updated_at"] = time.time()


def clear_designer_agent_cancel(*, user_id: Any) -> None:
    key = _user_key(user_id)
    with _lock:
        _cancel_requested.pop(key, None)


def is_designer_agent_cancel_requested(*, user_id: Any) -> bool:
    key = _user_key(user_id)
    with _lock:
        return bool(_cancel_requested.get(key))


def build_agent_cancelled_result(
    *,
    html_markup: str = "",
    css_stylesheet: str = "",
    js_script: str = "",
) -> dict[str, Any]:
    return {
        "assistant_message": "",
        "html_markup": html_markup,
        "css_stylesheet": css_stylesheet,
        "js_script": js_script,
        "agent_cancelled": True,
        "self_check": {"valid": True, "issues": []},
    }


def patch_live_progress(
    *,
    user_id: Any,
    agent_todos: list[dict[str, Any]] | None = None,
    work_plan: list[dict[str, Any]] | None = None,
    tool_step: dict[str, Any] | None = None,
    preview: dict[str, str] | None = None,
) -> None:
    key = _user_key(user_id)
    with _lock:
        cur = _by_user.get(key)
        if not cur or not cur.get("active"):
            return
        if agent_todos is not None:
            cur["agent_todos"] = [dict(t) for t in agent_todos]
        if work_plan is not None:
            cur["work_plan"] = [dict(s) for s in work_plan]
        if tool_step is not None:
            steps = list(cur.get("tool_steps") or [])
            steps.append(dict(tool_step))
            cur["tool_steps"] = steps[-32:]
        if preview is not None:
            cur["preview"] = {
                "html_markup": str(preview.get("html_markup") or ""),
                "css_stylesheet": str(preview.get("css_stylesheet") or ""),
                "js_script": str(preview.get("js_script") or ""),
            }
        cur["updated_at"] = time.time()


def end_live_progress(*, user_id: Any) -> None:
    key = _user_key(user_id)
    with _lock:
        cur = _by_user.get(key)
        if cur:
            cur["active"] = False
            cur["updated_at"] = time.time()


def clear_live_progress(*, user_id: Any) -> None:
    """Drop snapshot entirely (cancel / idle page load cleanup)."""
    key = _user_key(user_id)
    with _lock:
        _by_user.pop(key, None)


def get_live_progress(*, user_id: Any) -> dict[str, Any]:
    key = _user_key(user_id)
    with _lock:
        cur = _by_user.get(key)
        if not cur:
            return {"active": False, "agent_todos": [], "work_plan": [], "tool_steps": []}
        _coerce_inactive_if_ghost(cur)
        active = bool(cur.get("active"))
        out = {
            "active": active,
            "updated_at": cur.get("updated_at"),
            "agent_todos": list(cur.get("agent_todos") or []),
            "work_plan": list(cur.get("work_plan") or []),
            "tool_steps": list(cur.get("tool_steps") or []),
        }
        preview = cur.get("preview")
        if isinstance(preview, dict):
            out["preview"] = dict(preview)
        return out
