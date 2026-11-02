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


def initial_graph_state(
    *,
    message: str,
    history: list[dict[str, str]],
    html_markup: str,
    css_stylesheet: str,
    js_script: str,
    context_prefix: str,
    thread_id: str,
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
    }
