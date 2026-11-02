"""LangGraph + LangChain orchestration for Design Studio planner → executor → validator."""
from __future__ import annotations

import logging
import threading
from typing import Any

from django.conf import settings
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from apps.rfp_debate.meta_client import MetaModelClient

from .designer_executor_agent import DesignerExecutorAgent
from .designer_graph_checkmate import (
    DesignerGraphRoutingError,
    DesignerGraphTerminal,
    resolve_executor_terminal,
    resolve_planner_terminal,
    route_after_executor,
    route_after_planner,
    route_after_validator,
    route_graph_start,
    terminal_user_message,
)
from .designer_graph_callbacks import get_stream_callbacks, pop_stream_callbacks, push_stream_callbacks
from .designer_graph_checkpointer import (
    build_runnable_config,
    get_designer_checkpointer,
    read_latest_checkpoint_id,
)
from .designer_graph_state import (
    DesignerGraphState,
    build_graph_thread_id,
    initial_graph_state,
)
from .designer_planner_agent import DesignerPlannerAgent
from .designer_user_labels import GRAPH_PHASE_LABELS
from .designer_validator_agent import DesignerValidatorAgent
from .template_workspace import TemplateWorkspace

logger = logging.getLogger(__name__)

_graph_lock = threading.Lock()
_compiled_graph = None


def _callbacks(config: RunnableConfig | None) -> dict[str, Any]:
    cb = get_stream_callbacks()
    if cb:
        return cb
    if not config:
        return {}
    configurable = config.get("configurable") or {}
    return dict(configurable.get("stream_callbacks") or {})


def _tick_work(cb: dict[str, Any], step_id: str, status: str) -> None:
    fn = cb.get("on_work_step")
    if fn:
        fn(step_id, status)


def _append_graph_node(state: DesignerGraphState, name: str) -> list[str]:
    nodes = list(state.get("graph_nodes") or [])
    if name not in nodes:
        nodes.append(name)
    return nodes


def _merge_tool_traces(into: dict[str, Any], patch: dict[str, Any]) -> None:
    combined = list(into.get("tool_trace") or []) + list(patch.get("tool_trace") or [])
    if combined:
        into["tool_trace"] = combined[-40:]
        into["tool_steps"] = len(into["tool_trace"])


def _merge_repair_result(draft: dict[str, Any], repaired: dict[str, Any]) -> dict[str, Any]:
    assistant = str(repaired.get("assistant_message") or draft.get("assistant_message") or "").strip()
    merged = {
        **draft,
        "assistant_message": assistant,
        "html_markup": repaired.get("html_markup") or draft.get("html_markup") or "",
        "css_stylesheet": repaired.get("css_stylesheet") or draft.get("css_stylesheet") or "",
        "js_script": repaired.get("js_script") or draft.get("js_script") or "",
        "clarification_options": [],
    }
    _merge_tool_traces(merged, repaired)
    if repaired.get("model_api_error"):
        merged["model_api_error"] = True
        prior = str(draft.get("assistant_message") or "").strip()
        if prior and not prior.lower().startswith("design model api"):
            merged["assistant_message"] = (
                f"{prior}\n\n"
                "(Automatic validation repair timed out — preview shows your last successful edit.)"
            ).strip()
        elif (merged.get("html_markup") or "").strip():
            merged["assistant_message"] = (
                "Your proposal template was updated. "
                "Automatic validation repair timed out; you can Continue or edit manually."
            )
    return merged


def _validator_node(state: DesignerGraphState, config: RunnableConfig) -> dict[str, Any]:
    cb = _callbacks(config)
    result = dict(state.get("result") or {})
    nodes = _append_graph_node(state, "validator_agent")

    if cb.get("on_tool_event"):
        cb["on_tool_event"](
            {
                "tool": "validator_agent",
                "label": GRAPH_PHASE_LABELS["validator_agent"],
                "ok": True,
                "phase": "edit",
            }
        )

    validator = DesignerValidatorAgent(client=cb.get("meta_client"))
    if validator.should_skip(result):
        _tick_work(cb, "validate_repair", "skipped")
        return {
            "result": result,
            "terminal": DesignerGraphTerminal.VALIDATION_SKIPPED.value,
            "graph_nodes": nodes,
        }

    repair_passes = int(state.get("validation_repair_passes") or 0)
    max_passes = max(1, int(getattr(settings, "DESIGNER_SELF_CHECK_MAX_PASSES", 4)))
    _tick_work(cb, "validate_repair", "active")

    issues = validator.gather_issues(
        message=state.get("message") or "",
        history=state.get("history") or [],
        result=result,
    )

    if not issues:
        result["self_check"] = {"valid": True, "issues": [], "repair_passes": repair_passes}
        result.pop("validation_warnings", None)
        result["partial_completion"] = False
        result["continuation_recommended"] = False
        result.pop("model_api_error", None)
        result["remaining_items"] = []
        _tick_work(cb, "validate_repair", "done")
        return {
            "result": result,
            "validation_issues": [],
            "terminal": DesignerGraphTerminal.VALIDATION_PASSED.value,
            "graph_nodes": nodes,
        }

    if not getattr(settings, "DESIGNER_VALIDATOR_REPAIR_ENABLED", False):
        result["self_check"] = {
            "valid": False,
            "issues": issues,
            "repair_passes": repair_passes,
        }
        result["validation_warnings"] = issues
        _tick_work(cb, "validate_repair", "done")
        return {
            "result": result,
            "validation_issues": issues,
            "terminal": DesignerGraphTerminal.VALIDATION_MAX_PASSES.value,
            "graph_nodes": nodes,
        }

    if repair_passes >= max_passes:
        result["self_check"] = {
            "valid": False,
            "issues": issues,
            "repair_passes": repair_passes,
        }
        result["validation_warnings"] = issues
        _tick_work(cb, "validate_repair", "done")
        return {
            "result": result,
            "validation_issues": issues,
            "terminal": DesignerGraphTerminal.VALIDATION_MAX_PASSES.value,
            "graph_nodes": nodes,
        }

    return {
        "result": result,
        "validation_issues": issues,
        "terminal": DesignerGraphTerminal.VALIDATION_NEEDS_REPAIR.value,
        "graph_nodes": nodes,
    }


def _validator_repair_node(state: DesignerGraphState, config: RunnableConfig) -> dict[str, Any]:
    cb = _callbacks(config)
    issues = list(state.get("validation_issues") or [])
    result = dict(state.get("result") or {})
    nodes = _append_graph_node(state, "validator_repair")

    if cb.get("on_tool_event"):
        cb["on_tool_event"](
            {
                "tool": "validator_repair",
                "label": GRAPH_PHASE_LABELS["validator_repair"],
                "ok": True,
                "phase": "repair",
            }
        )

    executor = DesignerExecutorAgent(client=cb.get("meta_client"))
    try:
        repaired = executor.execute_repair(
            original_message=state.get("message") or "",
            issues=issues,
            html_markup=result.get("html_markup") or "",
            css_stylesheet=result.get("css_stylesheet") or "",
            js_script=result.get("js_script") or "",
            on_tool_event=cb.get("on_tool_event"),
            on_todo_event=None,
            on_preview_event=cb.get("on_preview_event"),
        )
    except BaseException as exc:
        logger.exception("LangGraph validator repair failed: %s", exc)
        repaired = {**result, "model_api_error": True}

    merged = _merge_repair_result(result, repaired)
    repair_passes = int(state.get("validation_repair_passes") or 0) + 1
    return {
        "result": merged,
        "validation_repair_passes": repair_passes,
        "graph_nodes": nodes,
    }


def _route_after_executor(state: DesignerGraphState) -> str:
    return route_after_executor(state)


def _route_after_validator(state: DesignerGraphState) -> str:
    return route_after_validator(state)


def _planner_node(state: DesignerGraphState, config: RunnableConfig) -> dict[str, Any]:
    cb = _callbacks(config)
    on_todo = cb.get("on_todo_event")
    on_tool = cb.get("on_tool_event")
    client = cb.get("meta_client")

    if on_tool:
        on_tool(
            {
                "tool": "planner_agent",
                "label": GRAPH_PHASE_LABELS["planner_agent"],
                "ok": True,
                "phase": "edit",
            }
        )

    planner = DesignerPlannerAgent(client=client)
    workspace = TemplateWorkspace(
        html_markup=state.get("html_markup") or "",
        css_stylesheet=state.get("css_stylesheet") or "",
        js_script=state.get("js_script") or "",
    )
    plan_error: BaseException | None = None
    plan_source = "fallback"
    plan_summary = ""
    todos: list[dict[str, Any]] = []
    try:
        plan = planner.create_plan(
            message=state.get("message") or "",
            workspace=workspace,
            context_prefix=state.get("context_prefix") or "",
            on_todo_event=on_todo,
        )
        plan_source = plan.source
        plan_summary = plan.summary
        todos = plan.todos
    except BaseException as exc:
        plan_error = exc
        logger.exception("LangGraph planner node failed: %s", exc)

    terminal = resolve_planner_terminal(plan_source=plan_source, todos=todos, error=plan_error)
    return {
        "execution_plan_todos": todos,
        "plan_source": plan_source,
        "plan_summary": plan_summary,
        "terminal": terminal.value,
        "graph_nodes": ["planner_agent"],
    }


def _executor_node(state: DesignerGraphState, config: RunnableConfig) -> dict[str, Any]:
    cb = _callbacks(config)
    client = cb.get("meta_client")
    executor = DesignerExecutorAgent(client=client)

    if cb.get("on_tool_event"):
        cb["on_tool_event"](
            {
                "tool": "executor_agent",
                "label": GRAPH_PHASE_LABELS["executor_agent"],
                "ok": True,
                "phase": "edit",
            }
        )

    try:
        result = executor.execute_plan(
            message=state.get("message") or "",
            history=state.get("history") or [],
            html_markup=state.get("html_markup") or "",
            css_stylesheet=state.get("css_stylesheet") or "",
            js_script=state.get("js_script") or "",
            context_prefix=state.get("context_prefix") or "",
            execution_plan_todos=state.get("execution_plan_todos") or [],
            on_work_step=cb.get("on_work_step"),
            on_tool_event=cb.get("on_tool_event"),
            on_todo_event=cb.get("on_todo_event"),
            on_preview_event=cb.get("on_preview_event"),
        )
    except BaseException as exc:
        logger.exception("LangGraph executor node failed: %s", exc)
        result = {
            "assistant_message": (
                "The design assistant hit an unexpected error while working on your proposal. "
                "Please try your request again."
            ),
            "html_markup": state.get("html_markup") or "",
            "css_stylesheet": state.get("css_stylesheet") or "",
            "js_script": state.get("js_script") or "",
            "model_api_error": True,
            "partial_completion": True,
            "continuation_recommended": True,
            "clarification_options": ["Retry the request", "Continue — finish the remaining edits"],
            "remaining_items": ["Complete header icons and layout fixes from your last message"],
        }

    terminal = resolve_executor_terminal(result)
    result["agent_mode"] = "langgraph"
    result["plan_source"] = state.get("plan_source") or ""
    result["plan_summary"] = state.get("plan_summary") or ""
    nodes = list(state.get("graph_nodes") or [])
    if "executor_agent" not in nodes:
        nodes.append("executor_agent")
    result["graph_nodes"] = nodes
    result["graph_terminal"] = terminal.value
    result["checkpoint_thread_id"] = state.get("graph_thread_id") or ""
    return {"result": result, "terminal": terminal.value, "graph_nodes": nodes}


def _continuation_node(state: DesignerGraphState, config: RunnableConfig) -> dict[str, Any]:
    cb = _callbacks(config)
    client = cb.get("meta_client")
    executor = DesignerExecutorAgent(client=client)
    result = executor.execute_continuation(
        message=state.get("message") or "",
        history=state.get("history") or [],
        html_markup=state.get("html_markup") or "",
        css_stylesheet=state.get("css_stylesheet") or "",
        js_script=state.get("js_script") or "",
        context_prefix=state.get("context_prefix") or "",
        on_work_step=cb.get("on_work_step"),
        on_tool_event=cb.get("on_tool_event"),
        on_todo_event=cb.get("on_todo_event"),
        on_preview_event=cb.get("on_preview_event"),
    )
    result["agent_mode"] = "langgraph_continuation"
    result["graph_nodes"] = ["executor_agent"]
    result["graph_terminal"] = DesignerGraphTerminal.CONTINUATION_DONE.value
    result["checkpoint_thread_id"] = state.get("graph_thread_id") or ""
    return {
        "result": result,
        "terminal": DesignerGraphTerminal.CONTINUATION_DONE.value,
        "graph_nodes": ["executor_agent"],
    }


def _abort_node(state: DesignerGraphState, config: RunnableConfig) -> dict[str, Any]:
    terminal = DesignerGraphTerminal.PLAN_FAILED
    msg = terminal_user_message(terminal) or "Planning failed."
    return {
        "result": {
            "assistant_message": msg,
            "html_markup": state.get("html_markup") or "",
            "css_stylesheet": state.get("css_stylesheet") or "",
            "js_script": state.get("js_script") or "",
            "clarification_options": ["Retry the request"],
            "graph_terminal": terminal.value,
            "graph_nodes": state.get("graph_nodes") or ["planner_agent"],
            "checkpoint_thread_id": state.get("graph_thread_id") or "",
        },
        "terminal": terminal.value,
    }


def _route_start(state: DesignerGraphState) -> str:
    return route_graph_start(state.get("message") or "")


def _route_after_planner(state: DesignerGraphState) -> str:
    raw = state.get("terminal") or DesignerGraphTerminal.IN_PROGRESS.value
    try:
        terminal = DesignerGraphTerminal(raw)
    except ValueError:
        terminal = DesignerGraphTerminal.PLAN_FAILED
    return route_after_planner(terminal)


def build_designer_langgraph(*, checkpointer=None):
    """Compiled LangGraph with checkpointer for thread resume."""
    graph = StateGraph(DesignerGraphState)
    graph.add_node("planner_agent", _planner_node)
    graph.add_node("executor_agent", _executor_node)
    graph.add_node("executor_continuation", _continuation_node)
    graph.add_node("validator_agent", _validator_node)
    graph.add_node("validator_repair", _validator_repair_node)
    graph.add_node("plan_abort", _abort_node)

    graph.add_conditional_edges(
        START,
        _route_start,
        {
            "planner": "planner_agent",
            "executor_continuation": "executor_continuation",
        },
    )
    graph.add_conditional_edges(
        "planner_agent",
        _route_after_planner,
        {
            "executor": "executor_agent",
            "end_abort": "plan_abort",
        },
    )
    graph.add_conditional_edges(
        "executor_agent",
        _route_after_executor,
        {
            "validator": "validator_agent",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "executor_continuation",
        _route_after_executor,
        {
            "validator": "validator_agent",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "validator_agent",
        _route_after_validator,
        {
            "validator_repair": "validator_repair",
            "end": END,
        },
    )
    graph.add_edge("validator_repair", "validator_agent")
    graph.add_edge("plan_abort", END)
    cp = checkpointer if checkpointer is not None else get_designer_checkpointer()
    return graph.compile(checkpointer=cp)


def get_compiled_designer_graph():
    global _compiled_graph
    with _graph_lock:
        if _compiled_graph is None:
            _compiled_graph = build_designer_langgraph()
        return _compiled_graph


def reset_compiled_designer_graph_for_tests() -> None:
    global _compiled_graph
    with _graph_lock:
        _compiled_graph = None


class DesignerAgentGraph:
    """Invoke compiled LangGraph with SSE callbacks and checkpoint thread ids."""

    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()
        self._graph = get_compiled_designer_graph()

    def run_edit_turn(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        context_prefix: str = "",
        graph_thread_id: str | None = None,
        user_id: int | str | None = None,
        template_id: str | None = None,
        on_work_step=None,
        on_tool_event=None,
        on_todo_event=None,
        on_preview_event=None,
    ) -> dict[str, Any]:
        thread_id = graph_thread_id
        if not thread_id:
            if user_id is None:
                user_id = "anon"
            thread_id = build_graph_thread_id(user_id=user_id, template_id=template_id)

        initial = initial_graph_state(
            message=message,
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            context_prefix=context_prefix,
            thread_id=thread_id,
        )
        config = build_runnable_config(thread_id=thread_id)
        token = push_stream_callbacks(
            {
                "meta_client": self.client,
                "on_work_step": on_work_step,
                "on_tool_event": on_tool_event,
                "on_todo_event": on_todo_event,
                "on_preview_event": on_preview_event,
            }
        )
        try:
            try:
                final_state = self._graph.invoke(initial, config=config)
            except DesignerGraphRoutingError as exc:
                return {
                    "assistant_message": str(exc),
                    "html_markup": html_markup,
                    "css_stylesheet": css_stylesheet,
                    "js_script": js_script,
                    "graph_terminal": exc.terminal.value,
                    "checkpoint_thread_id": thread_id,
                }
            result = dict(final_state.get("result") or {})
            if not result.get("assistant_message"):
                result.setdefault("assistant_message", "Design agent finished.")
            result.setdefault("checkpoint_thread_id", thread_id)
            ckpt_id = read_latest_checkpoint_id(self._graph, config)
            if ckpt_id:
                result["graph_checkpoint_id"] = ckpt_id
            return result
        finally:
            pop_stream_callbacks(token)

    def get_thread_state(self, thread_id: str) -> dict[str, Any] | None:
        """Read last checkpointed graph state for a designer thread (debug / resume)."""
        config = build_runnable_config(thread_id=thread_id)
        try:
            snap = self._graph.get_state(config)
        except Exception:
            return None
        if not snap or snap.values is None:
            return None
        return dict(snap.values)
