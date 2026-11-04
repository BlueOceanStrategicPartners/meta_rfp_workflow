"""Plain-language progress labels for Design Studio (non-technical users)."""
from __future__ import annotations

import re
from typing import Any

USER_TOOL_LABELS: dict[str, str] = {
    "get_template_overview": "Review how the proposal is organized",
    "list_template_symbols": "Find sections to update",
    "read_template_symbol": "Open a section to review",
    "read_template_lines": "Review part of the proposal",
    "search_template": "Search the proposal",
    "lint_template": "Lint the proposal",
    "replace_exact": "Apply a design change",
    "replace_lines": "Update a section",
    "append_template": "Add new content",
    "validate_template": "Run quality checks",
    "get_map_knowledge": "Load interactive map guidelines",
    "get_map_reference_code": "Load map demo code",
}

GRAPH_PHASE_LABELS: dict[str, str] = {
    "validator_agent": "Checking your design against the brief…",
    "validator_repair": "Fixing issues found during review…",
    "planner_agent": "Building your to-do list…",
    "executor_agent": "Working through your to-do list…",
    "model_turn": "Working on your design…",
}

PLANNER_LABEL_RULES = (
    "Write step labels for hotel sales and event planners — not developers. "
    "Use plain English to-do language (6–14 words). "
    "Do NOT mention HTML, CSS, JavaScript, templates, tools, LangGraph, validators, "
    "line numbers, symbols, or file names."
)

EXECUTION_PLAN_LABEL_RULES = PLANNER_LABEL_RULES


def user_tool_label(tool_name: str) -> str:
    key = str(tool_name or "").strip()
    if key in GRAPH_PHASE_LABELS:
        return GRAPH_PHASE_LABELS[key]
    return USER_TOOL_LABELS.get(key, key.replace("_", " ").strip().title() or "Working…")


def user_model_turn_label(*, turn: int, max_turns: int) -> str:
    _ = turn, max_turns
    return GRAPH_PHASE_LABELS["model_turn"]


def user_model_error_label(detail: str) -> str:
    snippet = (detail or "").strip()[:120]
    if snippet:
        return f"Muse Wonder hit a snag — try again in a moment."
    return "Muse Wonder is temporarily unavailable."


def format_user_tool_trace_summary(tool: str, result: dict[str, Any]) -> str:
    label = user_tool_label(tool)
    if not result.get("ok"):
        return f"{label} — needs another try."

    if tool == "replace_exact" and result.get("replacements"):
        n = int(result["replacements"])
        return f"{label} — {n} update{'s' if n != 1 else ''} applied."

    if tool == "replace_lines":
        return f"{label} — section updated."

    if tool == "search_template" and result.get("hits"):
        n = len(result["hits"])
        return f"{label} — found {n} spot{'s' if n != 1 else ''} to adjust."

    if tool == "validate_template":
        if result.get("valid"):
            return f"{label} — everything looks good."
        issues = result.get("issues") or []
        return f"{label} — {len(issues)} item{'s' if len(issues) != 1 else ''} still need attention."

    if tool == "lint_template":
        if result.get("valid"):
            return f"{label} — no issues."
        diags = result.get("diagnostics") or []
        first = diags[0] if diags else {}
        loc = f"{first.get('file', 'html')}:{first.get('line', '?')}" if first else "see diagnostics"
        return f"{label} — {len(diags)} issue(s); first at {loc}."

    if tool == "get_template_overview":
        return f"{label} — ready to edit."

    if tool == "list_template_symbols":
        shown = int(result.get("shown") or 0)
        return f"{label} — {shown} section{'s' if shown != 1 else ''} listed."

    if tool == "read_template_symbol":
        sym = result.get("symbol") or {}
        name = str(sym.get("name") or "section").strip()
        return f"{label} — {name}."

    if tool == "read_template_lines":
        return f"{label} — done."

    if tool == "append_template":
        return f"{label} — added."

    if tool == "get_map_knowledge":
        topic = str(result.get("topic") or "overview")
        return f"{label} — {topic.replace('_', ' ')}."

    if tool == "get_map_reference_code":
        part = str(result.get("part") or "code")
        return f"{label} — {part} excerpt loaded."

    return f"{label} — done."


_TECHNICAL_LABEL_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"langgraph", re.I), ""),
    (re.compile(r"\(langgraph\)", re.I), ""),
    (re.compile(r"validator\s*\([^)]*\)", re.I), "quality review"),
    (re.compile(r"calling design model[^.…]*", re.I), "Working on your design"),
    (re.compile(r"turn \d+ of \d+", re.I), ""),
    (re.compile(r"html,?\s*css,?\s*(and )?js", re.I), "the proposal design"),
    (re.compile(r"\btemplate\b", re.I), "proposal"),
    (re.compile(r"read template lines?", re.I), "Review part of the proposal"),
    (re.compile(r"append to template", re.I), "Add new content"),
    (re.compile(r"verify layout rules?", re.I), "Run quality checks"),
    (re.compile(r"search template", re.I), "Search the proposal"),
    (re.compile(r"planning agent", re.I), "Planning"),
    (re.compile(r"executor agent", re.I), "Muse Wonder"),
    (re.compile(r"design agent", re.I), "Muse Wonder"),
    (re.compile(r"\s{2,}", re.I), " "),
)


def sanitize_user_visible_label(text: str) -> str:
    """Last-resort cleanup for legacy or model-generated labels."""
    out = (text or "").strip()
    if not out:
        return out
    for pattern, repl in _TECHNICAL_LABEL_REPLACEMENTS:
        out = pattern.sub(repl, out)
    out = re.sub(r"\s+—\s+—", " — ", out).strip(" —")
    return out.strip() or "Working on your design…"
