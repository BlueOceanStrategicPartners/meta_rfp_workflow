"""Agent-owned task lists for Design Agent progress (SSE todo events)."""
from __future__ import annotations

from typing import Any, Literal

TodoStatus = Literal["pending", "active", "done", "skipped"]

INVESTIGATE_TOOLS = frozenset(
    {
        "get_template_overview",
        "list_template_symbols",
        "read_template_symbol",
        "search_template",
        "read_template_lines",
    }
)
MUTATE_TOOLS = frozenset({"replace_exact", "replace_lines", "append_template"})


def build_continuation_agent_todos() -> list[dict[str, Any]]:
    """User-visible steps after tapping Continue (align with frontend progress card)."""
    return [
        {
            "id": "investigate",
            "label": "Find what still needs to change",
            "status": "active",
        },
        {
            "id": "edit",
            "label": "Update the proposal design",
            "status": "pending",
        },
        {
            "id": "finalize",
            "label": "Finalize your proposal",
            "status": "pending",
        },
    ]


def build_agent_todos(message: str, *, repair_mode: bool = False) -> list[dict[str, Any]]:
    """Derive a user-visible task list from the designer request (agent work plan)."""
    if repair_mode:
        return [
            {"id": "triage", "label": "Review what needs fixing", "status": "pending"},
            {"id": "patch", "label": "Apply fixes to the proposal", "status": "pending"},
            {"id": "verify", "label": "Re-check until everything looks good", "status": "pending"},
        ]

    lower = (message or "").lower()
    todos: list[dict[str, Any]] = [
        {
            "id": "understand",
            "label": "Review your brief and the current proposal",
            "status": "pending",
        },
    ]

    if any(cue in lower for cue in ("create", "build", "design", "interactive", "new", "from scratch")):
        todos.append(
            {
                "id": "scaffold",
                "label": "Set up the proposal layout and sections",
                "status": "pending",
            }
        )

    styling_cues = (
        "link",
        "href",
        "header",
        "nav",
        "blue",
        "color",
        "css",
        "style",
        "hyperlink",
        "url",
        "classic",
    )
    if any(cue in lower for cue in styling_cues):
        todos.append(
            {
                "id": "investigate",
                "label": "Review navigation and styling in the proposal",
                "status": "pending",
            }
        )

    if any(cue in lower for cue in ("layout", "preview", "spacing", "font", "hero", "button", "cta")):
        todos.append(
            {
                "id": "layout",
                "label": "Adjust layout and component styling to match your brief",
                "status": "pending",
            }
        )

    todos.append(
        {
            "id": "edit",
            "label": "Update the proposal design",
            "status": "pending",
        }
    )

    if any(cue in lower for cue in ("map", "floorplan", "floor plan", "venue", "zone")):
        todos.append(
            {
                "id": "map",
                "label": "Align the venue map section with your assets and copy",
                "status": "pending",
            }
        )

    todos.append(
        {
            "id": "finalize",
            "label": "Finalize your proposal",
            "status": "pending",
        }
    )
    return todos


class AgentTodoTracker:
    def __init__(self, todos: list[dict[str, Any]]):
        self._todos = [dict(t) for t in todos]

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(t) for t in self._todos]

    def _index(self, todo_id: str) -> int:
        for i, todo in enumerate(self._todos):
            if todo.get("id") == todo_id:
                return i
        return -1

    def has(self, todo_id: str) -> bool:
        return self._index(todo_id) >= 0

    def status(self, todo_id: str) -> TodoStatus | None:
        idx = self._index(todo_id)
        if idx < 0:
            return None
        return self._todos[idx].get("status")  # type: ignore[return-value]

    def set_status(self, todo_id: str, status: TodoStatus) -> None:
        idx = self._index(todo_id)
        if idx < 0:
            return
        if status == "active":
            for i, todo in enumerate(self._todos):
                if todo.get("status") == "active" and i != idx:
                    todo["status"] = "pending"
        self._todos[idx]["status"] = status

    def activate_first_pending(self, *preferred_ids: str) -> None:
        for todo_id in preferred_ids:
            if self.has(todo_id) and self.status(todo_id) == "pending":
                self.set_status(todo_id, "active")
                return
        for todo in self._todos:
            if todo.get("status") == "pending":
                self.set_status(str(todo["id"]), "active")
                return

    def mark_all_done(self) -> None:
        for todo in self._todos:
            if todo.get("status") != "skipped":
                todo["status"] = "done"

    def pending_labels(self) -> list[str]:
        return [
            str(t.get("label") or t.get("id"))
            for t in self._todos
            if t.get("status") in ("pending", "active")
        ]

    def all_work_complete(self) -> bool:
        if not self._todos:
            return False
        return all(t.get("status") in ("done", "skipped") for t in self._todos)


def mark_finalize_todo_after_gate(tracker: AgentTodoTracker, *, valid: bool) -> None:
    """Legacy hook — Finalize completes on SSE wrap-up, not on validate_template."""
    del tracker, valid


def _complete_investigate_and_start_edit(tracker: AgentTodoTracker) -> None:
    if tracker.has("investigate") and tracker.status("investigate") != "done":
        tracker.set_status("investigate", "done")
    tracker.activate_first_pending("edit", "layout", "map")


def sync_todos_after_tool(
    tracker: AgentTodoTracker,
    *,
    tool_name: str,
    result: dict[str, Any],
    repair_mode: bool,
) -> None:
    ok = bool(result.get("ok"))
    tool = str(tool_name or "")

    if repair_mode:
        if tool in INVESTIGATE_TOOLS or tool == "validate_template":
            if tracker.status("triage") != "done":
                tracker.set_status("triage", "active")
            if ok and tool == "validate_template":
                tracker.set_status("triage", "done")
                tracker.activate_first_pending("patch")
        if tool in MUTATE_TOOLS:
            tracker.set_status("patch", "active")
            if ok:
                tracker.set_status("patch", "done")
                tracker.set_status("verify", "active")
        if tool == "validate_template":
            tracker.set_status("verify", "active")
            if ok and result.get("valid"):
                tracker.set_status("verify", "done")
        return

    if tool in INVESTIGATE_TOOLS:
        if tracker.has("investigate"):
            if tracker.status("investigate") == "pending":
                tracker.set_status("investigate", "active")
            if ok:
                _complete_investigate_and_start_edit(tracker)
        else:
            tracker.activate_first_pending("layout", "edit", "map")

    if tool == "get_template_overview" and not ok:
        err = str(result.get("error") or "").lower()
        if "blocked" in err and tracker.has("investigate"):
            _complete_investigate_and_start_edit(tracker)

    if tool in MUTATE_TOOLS or tool == "append_template":
        gate = result.get("validation_after_mutate")
        if ok:
            if tracker.has("scaffold") and tracker.status("scaffold") != "done":
                tracker.set_status("scaffold", "done")
            if tracker.has("investigate") and tracker.status("investigate") != "done":
                tracker.set_status("investigate", "done")
        if tracker.has("layout") and tracker.status("layout") == "pending":
            tracker.set_status("layout", "active")
        if tool in MUTATE_TOOLS or (tool == "append_template" and ok):
            tracker.set_status("edit", "active")
        if ok and tool in MUTATE_TOOLS:
            if tracker.has("layout") and tracker.status("layout") == "active":
                tracker.set_status("layout", "done")
            if tracker.status("edit") == "active":
                tracker.set_status("edit", "done")
                if tracker.has("finalize") and tracker.status("finalize") == "pending":
                    tracker.activate_first_pending("finalize")

    if tool == "validate_template":
        if tracker.has("finalize") and tracker.status("finalize") == "pending":
            tracker.set_status("finalize", "active")


def tool_mutated_template(tool_name: str, result: dict[str, Any]) -> bool:
    if tool_name in MUTATE_TOOLS and result.get("ok"):
        return True
    if tool_name == "append_template" and result.get("ok"):
        return True
    if tool_name == "replace_exact" and result.get("replacements"):
        return int(result["replacements"]) > 0
    return False
