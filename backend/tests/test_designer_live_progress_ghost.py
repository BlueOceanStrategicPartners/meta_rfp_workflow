import time

from apps.designer_studio import designer_live_progress as mod
from apps.designer_studio.designer_live_progress import (
    begin_live_progress,
    clear_live_progress,
    get_live_progress,
    patch_live_progress,
)


def test_ghost_active_cleared_when_no_work():
    uid = 7001
    begin_live_progress(user_id=uid)
    snap = get_live_progress(user_id=uid)
    assert snap["active"] is True

    with mod._lock:
        cur = mod._by_user[str(uid)]
        cur["updated_at"] = time.time() - mod.GHOST_ACTIVE_SECONDS - 1.0

    snap2 = get_live_progress(user_id=uid)
    assert snap2["active"] is False
    clear_live_progress(user_id=uid)


def test_active_with_todos_not_cleared_as_ghost():
    uid = 7002
    begin_live_progress(user_id=uid)
    patch_live_progress(
        user_id=uid,
        agent_todos=[{"id": "exec_1", "label": "Edit", "status": "active"}],
    )
    snap = get_live_progress(user_id=uid)
    assert snap["active"] is True
    assert len(snap["agent_todos"]) == 1
    clear_live_progress(user_id=uid)
