"""Planning agent — one-shot LLM todo list from user brief + template context (no tools).

This agent never edits HTML/CSS/JS. Output feeds the executor agent only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.rfp_debate.meta_client import MetaModelClient

from .agent_execution_plan import (
    fallback_agent_todos,
    planning_wait_todos,
    try_refine_execution_plan_with_llm,
)
from .agent_task_plan import AgentTodoTracker
from .designer_user_labels import PLANNER_LABEL_RULES
from .template_workspace import TemplateWorkspace

logger = logging.getLogger(__name__)

TodoEventCallback = Any  # Callable[[list[dict[str, Any]]], None] — avoid circular import

PLANNER_AGENT_SYSTEM = (
    "You are the Design Studio planning assistant. Your ONLY job is a clear, ordered to-do list "
    "for a separate design agent that updates the hospitality proposal behind the scenes.\n"
    "You do NOT edit the proposal yourself. You do NOT call tools. One JSON response only.\n\n"
    "Return JSON only:\n"
    '{"steps":[{"id":"exec_1","label":"Short user-facing step (6-14 words)"}, ...], "summary":"one line"}\n'
    "Rules:\n"
    f"- {PLANNER_LABEL_RULES}\n"
    "- Localized fixes (nav, icons, map, styling): EXACTLY 3 steps — locate → change → polish.\n"
    "- Large new builds: up to 5-7 steps.\n"
    "- Do NOT include a final quality-check step — the platform adds that automatically.\n"
    "- ids must be exec_1, exec_2, ... sequentially.\n"
    "- Use the proposal snapshot and designer request; respect rules and attachments in context.\n"
    "- For empty proposals, first step must add structure before styling.\n"
    "- Steps must reflect what the user asked (nav, branding, map, dates, etc.).\n"
)


@dataclass
class PlannerAgentResult:
    todos: list[dict[str, Any]]
    summary: str
    source: str  # "llm" | "fallback"


class DesignerPlannerAgent:
    """One-shot planner (Cursor-style plan pass before execution)."""

    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    def planning_wait_todos(self) -> list[dict[str, Any]]:
        return planning_wait_todos()

    def create_plan(
        self,
        *,
        message: str,
        workspace: TemplateWorkspace,
        context_prefix: str = "",
        on_todo_event: TodoEventCallback | None = None,
    ) -> PlannerAgentResult:
        """Single LLM call → agent todo list for SSE + executor."""
        if on_todo_event:
            on_todo_event(self.planning_wait_todos())

        llm_todos = try_refine_execution_plan_with_llm(
            message=message,
            workspace=workspace,
            context_prefix=context_prefix,
            active_exec_id=None,
            system_prompt=PLANNER_AGENT_SYSTEM,
            client=self.client,
        )
        if llm_todos:
            summary = "Execution plan from planning agent"
            if on_todo_event:
                on_todo_event(llm_todos)
            return PlannerAgentResult(todos=llm_todos, summary=summary, source="llm")

        logger.warning("Planning agent could not produce LLM plan; using heuristic fallback todos")
        fallback = fallback_agent_todos(message, repair_mode=False)
        tracker = AgentTodoTracker(fallback)
        tracker.activate_first_pending()
        todos = tracker.snapshot()
        if on_todo_event:
            on_todo_event(todos)
        return PlannerAgentResult(
            todos=todos,
            summary="Heuristic plan (planning model unavailable)",
            source="fallback",
        )


def todos_from_planner_result(result: PlannerAgentResult) -> list[dict[str, Any]]:
    return [dict(t) for t in result.todos]
