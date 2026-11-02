"""Executor agent — tool-calling loop that completes a planner-produced todo list."""
from __future__ import annotations

from typing import Any

from apps.rfp_debate.meta_client import MetaModelClient

from .design_agent_tool_loop import (
    DesignerToolLoopRunner,
    PreviewEventCallback,
    TodoEventCallback,
    ToolEventCallback,
    WorkStepCallback,
)


class DesignerExecutorAgent:
    """Runs template edits via tools; never replans (plan is fixed at entry)."""

    def __init__(self, client: MetaModelClient | None = None):
        self._runner = DesignerToolLoopRunner(client=client)

    def execute_plan(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        context_prefix: str,
        execution_plan_todos: list[dict[str, Any]],
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
        user_id: int | str | None = None,
        graph_thread_id: str | None = None,
        executor_session_resumed: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._runner.run_with_plan(
            message=message,
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            context_prefix=context_prefix,
            execution_plan_todos=execution_plan_todos,
            on_work_step=on_work_step,
            on_tool_event=on_tool_event,
            on_todo_event=on_todo_event,
            on_preview_event=on_preview_event,
            user_id=user_id,
            graph_thread_id=graph_thread_id,
            executor_session_resumed=executor_session_resumed,
        )

    def execute_repair(
        self,
        *,
        original_message: str,
        issues: list[str],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
        user_id: int | str | None = None,
        graph_thread_id: str | None = None,
        executor_session_resumed: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._runner.run_repair(
            original_message=original_message,
            issues=issues,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            on_work_step=on_work_step,
            on_tool_event=on_tool_event,
            on_todo_event=on_todo_event,
            on_preview_event=on_preview_event,
            user_id=user_id,
            graph_thread_id=graph_thread_id,
            executor_session_resumed=executor_session_resumed,
        )

    def execute_continuation(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        context_prefix: str,
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
        user_id: int | str | None = None,
        graph_thread_id: str | None = None,
        executor_session_resumed: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._runner.run(
            message=message,
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            context_prefix=context_prefix,
            on_work_step=on_work_step,
            on_tool_event=on_tool_event,
            on_todo_event=on_todo_event,
            on_preview_event=on_preview_event,
            user_id=user_id,
            graph_thread_id=graph_thread_id,
            executor_session_resumed=executor_session_resumed,
        )
