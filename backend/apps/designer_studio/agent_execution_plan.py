"""LLM-first execution plans for Design Agent tool loop (shown via SSE todos)."""
from __future__ import annotations

import logging
import re
from typing import Any

from django.conf import settings

from apps.rfp_debate.meta_client import MetaModelClient

logger = logging.getLogger(__name__)

from .agent_task_plan import (
    INVESTIGATE_TOOLS,
    MUTATE_TOOLS,
    AgentTodoTracker,
    sync_todos_after_tool,
)
from .designer_fast_edit import merge_duplicate_plan_labels, trim_execution_steps_for_request
from .designer_user_labels import EXECUTION_PLAN_LABEL_RULES
from .template_workspace import TemplateWorkspace
from .tool_loop_context import format_workspace_context_anchor

PLAN_STEP_ID = "plan"
MAX_EXEC_STEPS = 8

EXECUTION_PLAN_SYSTEM = (
    "You plan how a hospitality proposal designer will fulfill a user request. "
    "The executor edits the proposal behind the scenes — users only see your step labels.\n"
    "Return JSON only:\n"
    '{"steps":[{"id":"exec_1","label":"Short user-facing step (6-14 words)"}, ...], "summary":"one line"}\n'
    "Rules:\n"
    f"- {EXECUTION_PLAN_LABEL_RULES}\n"
    "- For localized fixes (nav, icons, map, colors, buttons): use EXACTLY 3 steps — "
    "locate the area → apply the change → quick polish. Do not add extra review-only steps.\n"
    "- For large new builds or empty proposals: up to 5-7 steps (structure → styling → sections).\n"
    "- Provide 3-7 concrete steps in execution order (review → updates → polish).\n"
    "- Do NOT include a final wrap-up step — the platform appends Finalize automatically.\n"
    "- ids must be exec_1, exec_2, ... sequentially.\n"
    "- Respect agent rules and attachments mentioned in the user message.\n"
    "- For empty proposals, first step must add structure before styling.\n"
)


def planning_wait_todos() -> list[dict[str, Any]]:
    """Transient SSE state while the planning agent generates the task list."""
    return [
        {
            "id": "planning",
            "label": "Creating your to-do list from this request…",
            "status": "active",
        },
    ]


def planning_placeholder_todos() -> list[dict[str, Any]]:
    """Backward-compatible alias for tests."""
    return planning_wait_todos()


def _normalize_llm_steps(raw_steps: Any) -> list[dict[str, str]]:
    if not isinstance(raw_steps, list):
        return []
    out: list[dict[str, str]] = []
    for i, item in enumerate(raw_steps[:MAX_EXEC_STEPS], start=1):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        step_id = str(item.get("id") or f"exec_{i}").strip()
        if not re.match(r"^exec_\d+$", step_id):
            step_id = f"exec_{i}"
        out.append({"id": step_id, "label": label[:140]})
    return out


def build_todos_from_execution_steps(exec_steps: list[dict[str, str]]) -> list[dict[str, Any]]:
    todos: list[dict[str, Any]] = []
    for step in exec_steps:
        todos.append(
            {
                "id": step["id"],
                "label": step["label"],
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


def _activate_first_exec_step(todos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [dict(t) for t in todos]
    for todo in out:
        if todo.get("status") == "pending":
            todo["status"] = "active"
            break
    return out


def try_refine_execution_plan_with_llm(
    *,
    message: str,
    workspace: TemplateWorkspace,
    context_prefix: str,
    active_exec_id: str | None = None,
    system_prompt: str | None = None,
    client: MetaModelClient | None = None,
) -> list[dict[str, Any]] | None:
    if not settings.USE_FIXTURE_DEBATE and not getattr(settings, "META_MODEL_API_KEY", ""):
        return None
    anchor = format_workspace_context_anchor(workspace, message=message)
    rules_bit = (context_prefix or "")[:4000]
    user_content = (
        f"Template snapshot:\n{anchor[:6000]}\n\n"
        f"Agent context (rules, attachments, audit):\n{rules_bit}\n\n"
        f"Designer request:\n{(message or '')[:2500]}"
    )
    llm_client = client or MetaModelClient()
    prompt = system_prompt or EXECUTION_PLAN_SYSTEM
    try:
        raw = llm_client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            fixture_kind="designer_execution_plan",
        )
    except Exception as exc:
        logger.warning("Execution plan LLM refine failed, keeping heuristic plan: %s", exc)
        return None
    parsed = _normalize_llm_steps(raw.get("steps") if isinstance(raw, dict) else None)
    parsed = merge_duplicate_plan_labels(parsed)
    max_simple = int(getattr(settings, "DESIGNER_EXEC_PLAN_MAX_SIMPLE_STEPS", 3))
    max_standard = int(getattr(settings, "DESIGNER_EXEC_PLAN_MAX_STANDARD_STEPS", 5))
    parsed = trim_execution_steps_for_request(
        message,
        parsed,
        max_simple=max_simple,
        max_standard=max_standard,
    )
    if not parsed:
        return None
    todos = _activate_first_exec_step(build_todos_from_execution_steps(parsed))
    if active_exec_id:
        for todo in todos:
            if str(todo.get("id") or "").startswith("exec_"):
                todo["status"] = "pending"
        if any(str(t.get("id")) == active_exec_id for t in todos):
            for todo in todos:
                tid = str(todo.get("id") or "")
                if tid == active_exec_id:
                    todo["status"] = "active"
                    break
        else:
            todos = _activate_first_exec_step(todos)
    return todos


def generate_execution_plan(
    *,
    message: str,
    workspace: TemplateWorkspace,
    context_prefix: str = "",
) -> list[dict[str, Any]]:
    """Return agent todos from the design model execution-plan call (SSE todo source of truth)."""
    refined = try_refine_execution_plan_with_llm(
        message=message,
        workspace=workspace,
        context_prefix=context_prefix,
        active_exec_id=None,
    )
    if refined:
        return refined
    logger.warning("Execution plan unavailable from design model; tool loop will run without exec todos")
    return []


def uses_execution_plan_todos(todos: list[dict[str, Any]]) -> bool:
    return any(str(t.get("id") or "").startswith("exec_") for t in todos)


def format_execution_plan_for_prompt(tracker: AgentTodoTracker) -> str:
    lines = ["EXECUTION PLAN (complete steps in order; tools should serve the ACTIVE step):"]
    active_idx = 0
    for i, todo in enumerate(tracker.snapshot(), start=1):
        status = str(todo.get("status") or "pending")
        if status == "active":
            active_idx = i
        tag = status.upper()
        label = str(todo.get("label") or todo.get("id"))
        lines.append(f"{i}. [{tag}] {label}")
    if active_idx:
        lines.append(
            f"\nFocus this turn on step {active_idx} only unless a tool failure requires a quick re-read."
        )
    return "\n".join(lines)


def format_plan_focus_nudge(tracker: AgentTodoTracker) -> str:
    for i, todo in enumerate(tracker.snapshot(), start=1):
        if todo.get("status") == "active":
            label = str(todo.get("label") or todo.get("id"))
            return f"PLAN FOCUS: Step {i} — {label}. Prefer tools that advance this step."
    return ""


def _advance_active_exec_step(tracker: AgentTodoTracker) -> None:
    todos = tracker.snapshot()
    for i, todo in enumerate(todos):
        if todo.get("status") != "active":
            continue
        step_id = str(todo.get("id") or "")
        if step_id == PLAN_STEP_ID:
            return
        tracker.set_status(step_id, "done")
        for nxt in todos[i + 1 :]:
            nid = str(nxt.get("id") or "")
            if nxt.get("status") == "pending" and nid != "finalize":
                tracker.set_status(nid, "active")
                return
        if tracker.has("finalize") and tracker.status("finalize") == "pending":
            tracker.set_status("finalize", "active")
        return


def sync_execution_plan_after_tool(
    tracker: AgentTodoTracker,
    *,
    tool_name: str,
    result: dict[str, Any],
    repair_mode: bool,
) -> None:
    if repair_mode or not uses_execution_plan_todos(tracker.snapshot()):
        sync_todos_after_tool(
            tracker,
            tool_name=tool_name,
            result=result,
            repair_mode=repair_mode,
        )
        return

    ok = bool(result.get("ok"))
    tool = str(tool_name or "")

    if tool == "validate_template":
        return

    if not ok:
        return

    if tool in MUTATE_TOOLS or tool == "append_template":
        gate = result.get("validation_after_mutate")
        if isinstance(gate, dict) and gate.get("valid") is False:
            return
        _advance_active_exec_step(tracker)
        return

    if tool in INVESTIGATE_TOOLS:
        active = next((t for t in tracker.snapshot() if t.get("status") == "active"), None)
        if not active:
            return
        label = str(active.get("label") or "").lower()
        if any(
            kw in label
            for kw in (
                "inspect",
                "locate",
                "review",
                "understand",
                "search",
                "read",
                "snapshot",
                "template",
            )
        ):
            _advance_active_exec_step(tracker)


def fallback_agent_todos(message: str, *, repair_mode: bool) -> list[dict[str, Any]]:
    return build_agent_todos(message, repair_mode=repair_mode)
