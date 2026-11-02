from apps.designer_studio.agent_task_plan import (
    AgentTodoTracker,
    build_continuation_agent_todos,
    sync_todos_after_tool,
)


def test_blocked_overview_advances_continue_todos():
    tracker = AgentTodoTracker(build_continuation_agent_todos())
    assert tracker.status("investigate") == "active"
    sync_todos_after_tool(
        tracker,
        tool_name="get_template_overview",
        result={"ok": False, "error": "get_template_overview is blocked during Continue"},
        repair_mode=False,
    )
    assert tracker.status("investigate") == "done"
    assert tracker.status("edit") == "active"


def test_list_symbols_completes_investigate():
    tracker = AgentTodoTracker(build_continuation_agent_todos())
    sync_todos_after_tool(
        tracker,
        tool_name="list_template_symbols",
        result={"ok": True, "shown": 3},
        repair_mode=False,
    )
    assert tracker.status("investigate") == "done"
    assert tracker.status("edit") == "active"


def test_mutate_completes_edit():
    tracker = AgentTodoTracker(build_continuation_agent_todos())
    sync_todos_after_tool(
        tracker,
        tool_name="list_template_symbols",
        result={"ok": True},
        repair_mode=False,
    )
    sync_todos_after_tool(
        tracker,
        tool_name="replace_exact",
        result={"ok": True, "replacements": 1},
        repair_mode=False,
    )
    assert tracker.status("edit") == "done"
    assert tracker.status("finalize") == "active"
