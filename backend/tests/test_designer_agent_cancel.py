from apps.designer_studio.designer_live_progress import (
    begin_live_progress,
    clear_designer_agent_cancel,
    end_live_progress,
    get_live_progress,
    is_designer_agent_cancel_requested,
    request_designer_agent_cancel,
)


def test_request_cancel_stops_live_progress_and_tool_loop_flag():
    uid = 4242
    begin_live_progress(user_id=uid)
    assert get_live_progress(user_id=uid)["active"] is True
    request_designer_agent_cancel(user_id=uid)
    assert is_designer_agent_cancel_requested(user_id=uid) is True
    snap = get_live_progress(user_id=uid)
    assert snap["active"] is False
    clear_designer_agent_cancel(user_id=uid)
    assert is_designer_agent_cancel_requested(user_id=uid) is False
    end_live_progress(user_id=uid)


def test_begin_live_progress_clears_stale_cancel():
    uid = 99
    request_designer_agent_cancel(user_id=99)
    begin_live_progress(user_id=uid)
    assert is_designer_agent_cancel_requested(user_id=uid) is False
