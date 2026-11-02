"""Dedicated TypedDicts for Design Studio LangGraph state and checkpoint config."""
from __future__ import annotations

from typing import Any, TypedDict

# LangGraph configurable keys (must be JSON-serializable where persisted)
CHECKPOINT_NS_DESIGNER = "designer_studio_v1"


class DesignerGraphTurnInput(TypedDict, total=False):
    """User turn payload entering the graph."""

    message: str
    history: list[dict[str, str]]
    html_markup: str
    css_stylesheet: str
    js_script: str
    context_prefix: str


class DesignerGraphPlanSlice(TypedDict, total=False):
    """Planner node output (checkpointed between planner → executor)."""

    execution_plan_todos: list[dict[str, Any]]
    plan_summary: str
    plan_source: str


class DesignerGraphExecutorSessionSlice(TypedDict, total=False):
    """Checkpointed executor memory — survives tool-loop message condensation across turns."""

    executor_session: dict[str, Any]


class DesignerGraphRunMeta(TypedDict, total=False):
    """Graph control metadata (not LangGraph reserved keys)."""

    graph_nodes: list[str]
    terminal: str
    graph_thread_id: str


class DesignerGraphValidationSlice(TypedDict, total=False):
    """Validator ↔ repair loop (checkpointed each pass)."""

    validation_issues: list[str]
    validation_repair_passes: int


class DesignerGraphResultSlice(TypedDict, total=False):
    """Executor / abort terminal payload."""

    result: dict[str, Any]


class DesignerGraphState(
    DesignerGraphTurnInput,
    DesignerGraphPlanSlice,
    DesignerGraphExecutorSessionSlice,
    DesignerGraphRunMeta,
    DesignerGraphValidationSlice,
    DesignerGraphResultSlice,
    total=False,
):
    """Full LangGraph state (merge of dedicated slices)."""


class DesignerGraphConfigurable(TypedDict, total=False):
    """RunnableConfig.configurable — thread_id required when checkpointer enabled."""

    thread_id: str
    checkpoint_id: str


def build_graph_thread_id(*, user_id: int | str, template_id: str | None = None) -> str:
    tid = str(template_id).strip() if template_id else "draft"
    return f"designer-{user_id}-{tid}"


def resolve_template_langgraph_thread_id(
    *,
    user_id: int | str | None,
    template_id: str | None,
    stored_thread_id: str | None = None,
) -> str:
    """One stable LangGraph checkpoint thread per template (industry default for durable agent sessions)."""
    stored = (stored_thread_id or "").strip()
    if stored:
        return stored
    uid = user_id if user_id is not None else "anon"
    return build_graph_thread_id(user_id=uid, template_id=template_id)

def initial_graph_state(
    *,
    message: str,
    history: list[dict[str, str]],
    html_markup: str,
    css_stylesheet: str,
    js_script: str,
    context_prefix: str,
    thread_id: str,
    user_id: int | str | None = None,
) -> DesignerGraphState:
    from .designer_graph_checkmate import DesignerGraphTerminal

    return {
        "message": message,
        "history": history,
        "html_markup": html_markup,
        "css_stylesheet": css_stylesheet,
        "js_script": js_script,
        "context_prefix": context_prefix,
        "terminal": DesignerGraphTerminal.IN_PROGRESS.value,
        "graph_thread_id": thread_id,
        "user_id": user_id,
    }
