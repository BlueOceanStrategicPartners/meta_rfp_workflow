from apps.designer_studio.agent_task_plan import (
    AgentTodoTracker,
    build_agent_todos,
    sync_todos_after_tool,
)


def test_build_agent_todos_includes_investigate_for_link_issues():
    todos = build_agent_todos("Fix blue hyperlinks in the header nav")
    ids = [t["id"] for t in todos]
    assert "investigate" in ids
    assert "finalize" in ids


def test_sync_todos_marks_investigate_done_after_search():
    tracker = AgentTodoTracker(build_agent_todos("Fix header link colors"))
    tracker.set_status("understand", "done")
    tracker.set_status("investigate", "active")
    sync_todos_after_tool(
        tracker,
        tool_name="search_template",
        result={"ok": True, "hits": [{"line": 1}]},
        repair_mode=False,
    )
    assert tracker.status("investigate") == "done"
    assert tracker.status("edit") == "active"


def test_sync_todos_repair_mode_validate_completes_verify():
    tracker = AgentTodoTracker(build_agent_todos("", repair_mode=True))
    tracker.set_status("triage", "done")
    tracker.set_status("patch", "done")
    sync_todos_after_tool(
        tracker,
        tool_name="validate_template",
        result={"ok": True, "valid": True},
        repair_mode=True,
    )
    assert tracker.status("verify") == "done"
