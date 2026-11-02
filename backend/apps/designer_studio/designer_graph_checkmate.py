"""Checkmate execution paths for Designer multi-agent LangGraph (terminal states).

Maps happy / edge / worst-case branches to deterministic graph routing — aligned with
Docs/Multi_Agent_Rfp_Engine_Development_Plan_2466.md §9 and Designer_Agent_Tool_Loop_Roadmap.md.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from apps.rfp_debate.muse_completion import MuseStructuredValidationError

from .tool_loop_context import user_wants_continuation


class DesignerGraphTerminal(str, Enum):
    """Every graph branch must land in one of these states."""

    IN_PROGRESS = "in_progress"
    PLAN_READY = "plan_ready"
    PLAN_FALLBACK = "plan_fallback"
    PLAN_FAILED = "plan_failed"
    EXECUTOR_DONE = "executor_done"
    EXECUTOR_PARTIAL = "executor_partial"
    EXECUTOR_FAILED = "executor_failed"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_SKIPPED = "validation_skipped"
    VALIDATION_NEEDS_REPAIR = "validation_needs_repair"
    VALIDATION_MAX_PASSES = "validation_max_passes"
    CONTINUATION_DONE = "continuation_done"


class DesignerGraphRoutingError(Exception):
    """Unrecoverable graph branch — surfaced to chat as error payload."""

    def __init__(self, code: str, message: str, *, terminal: DesignerGraphTerminal):
        super().__init__(message)
        self.code = code
        self.terminal = terminal


PlannerRoute = Literal["executor", "end_abort"]
StartRoute = Literal["planner", "executor_continuation"]
ExecutorRoute = Literal["validator", "end"]
ValidatorRoute = Literal["validator_repair", "end"]


def route_graph_start(message: str) -> StartRoute:
    """Checkmate: continuation bypasses planner (edge: user tapped Continue)."""
    if user_wants_continuation(message or ""):
        return "executor_continuation"
    return "planner"


def resolve_planner_terminal(
    *,
    plan_source: str,
    todos: list[dict[str, Any]],
    error: BaseException | None = None,
) -> DesignerGraphTerminal:
    """Happy: LLM plan. Edge: heuristic fallback. Worst: hard failure."""
    if error is not None:
        if isinstance(error, MuseStructuredValidationError):
            return DesignerGraphTerminal.PLAN_FALLBACK
        return DesignerGraphTerminal.PLAN_FAILED
    if plan_source == "llm" and todos:
        return DesignerGraphTerminal.PLAN_READY
    if todos:
        return DesignerGraphTerminal.PLAN_FALLBACK
    return DesignerGraphTerminal.PLAN_FAILED


def route_after_planner(terminal: DesignerGraphTerminal) -> PlannerRoute:
    """Worst-case plan failure still attempts executor with empty plan blocked here."""
    if terminal == DesignerGraphTerminal.PLAN_FAILED:
        return "end_abort"
    return "executor"


def resolve_executor_terminal(result: dict[str, Any]) -> DesignerGraphTerminal:
    """Classify executor tool-loop outcome."""
    if result.get("model_api_error"):
        return DesignerGraphTerminal.EXECUTOR_FAILED
    if result.get("tool_loop_exhausted") or result.get("partial_completion"):
        return DesignerGraphTerminal.EXECUTOR_PARTIAL
    return DesignerGraphTerminal.EXECUTOR_DONE


def route_after_executor(state: dict[str, Any]) -> ExecutorRoute:
    """All successful executor paths enter validator (checkpointed); hard failures skip repair graph."""
    result = state.get("result") or {}
    from .designer_validation import should_skip_post_executor_validation

    if should_skip_post_executor_validation(result):
        return "end"
    return "validator"


def route_after_validator(state: dict[str, Any]) -> ValidatorRoute:
    from django.conf import settings

    terminal_raw = state.get("terminal") or ""
    try:
        terminal = DesignerGraphTerminal(terminal_raw)
    except ValueError:
        return "end"
    if terminal in (
        DesignerGraphTerminal.VALIDATION_PASSED,
        DesignerGraphTerminal.VALIDATION_SKIPPED,
        DesignerGraphTerminal.VALIDATION_MAX_PASSES,
    ):
        return "end"
    if terminal == DesignerGraphTerminal.VALIDATION_NEEDS_REPAIR:
        if not getattr(settings, "DESIGNER_VALIDATOR_REPAIR_ENABLED", False):
            return "end"
        passes = int(state.get("validation_repair_passes") or 0)
        max_passes = max(1, int(getattr(settings, "DESIGNER_SELF_CHECK_MAX_PASSES", 4)))
        if passes >= max_passes:
            return "end"
        return "validator_repair"
    return "end"


def terminal_user_message(terminal: DesignerGraphTerminal) -> str | None:
    if terminal == DesignerGraphTerminal.PLAN_FAILED:
        return (
            "Planning agent could not build a task list. "
            "Try a shorter message or retry in a moment."
        )
    return None
