"""Fast-edit helpers: tighter plans, edit-target hints, read-only steering."""
from __future__ import annotations

import re
from typing import Any

from .agent_rules import hybrid_query_document_score
from .template_symbol_index import index_template_file
from .template_workspace import TemplateWorkspace

MAX_EDIT_HINTS = 14

_LOCALIZED_CUES = (
    "fix",
    "update",
    "change",
    "color",
    "nav",
    "header",
    "icon",
    "map",
    "button",
    "cta",
    "link",
    "spacing",
    "align",
    "style",
    "font",
    "logo",
)

_GREENFIELD_CUES = (
    "from scratch",
    "create new",
    "build new",
    "greenfield",
    "empty template",
    "new proposal",
)


def is_localized_edit_request(message: str) -> bool:
    lower = (message or "").lower()
    if any(c in lower for c in _GREENFIELD_CUES):
        return False
    if len(message or "") > 1200:
        return False
    return any(c in lower for c in _LOCALIZED_CUES)


def trim_execution_steps_for_request(
    message: str,
    steps: list[dict[str, str]],
    *,
    max_simple: int = 3,
    max_standard: int = 5,
) -> list[dict[str, str]]:
    """Keep plans short for typical three-file surgical edits."""
    if not steps:
        return steps
    cap = max_simple if is_localized_edit_request(message) else max_standard
    return steps[:cap]


def _queries_from_message(message: str) -> list[str]:
    lower = (message or "").lower()
    queries: list[str] = []
    if any(k in lower for k in ("nav", "icon", "header", "menu", "hyperlink")):
        queries.extend(["nav", "icon", "header", "icon-btn", "nav-icons"])
    if any(k in lower for k in ("map", "floor", "venue", "floorplan")):
        queries.extend(["map", "venue", "floor", "mapSlot", "map-fallback"])
    if any(k in lower for k in ("button", "cta", "accept", "link")):
        queries.extend(["cta", "accept", "proposal-cta", "button"])
    if any(k in lower for k in ("color", "brand", "style", "css")):
        queries.extend(["brand", "hero", "nav", "color"])
    if not queries:
        queries = ["header", "nav", "map", "cta"]
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def format_edit_target_hints(workspace: TemplateWorkspace, message: str = "") -> str:
    """Pre-index likely edit locations so the model skips search/read loops."""
    queries = _queries_from_message(message)
    lines: list[str] = [
        "EDIT TARGET HINTS (use read_template_symbol(symbol_id) then patch — "
        "do not run more than one search pass for the same target):"
    ]
    seen_ids: set[str] = set()
    for file in ("html", "css", "js"):
        try:
            syms = index_template_file(workspace, file)
        except (ValueError, TypeError):
            continue
        if file == "html":
            sections = [s for s in syms if s.kind == "proposal_section"]
            if sections and (message or "").strip():
                ranked = sorted(
                    sections,
                    key=lambda s: hybrid_query_document_score(
                        message, f"{s.name} {s.preview}"
                    ),
                    reverse=True,
                )
                sections = ranked
            for sym in sections:
                if queries and not any(
                    q.lower() in f"{sym.name} {sym.preview}".lower() for q in queries
                ):
                    if hybrid_query_document_score(message, f"{sym.name} {sym.preview}") < 0.12:
                        continue
                if sym.id in seen_ids:
                    continue
                seen_ids.add(sym.id)
                lines.append(
                    f"  • {sym.id} — {sym.name} (section lines {sym.start_line}-{sym.end_line})"
                )
                if len(seen_ids) >= MAX_EDIT_HINTS:
                    break
            if len(seen_ids) >= MAX_EDIT_HINTS:
                break
        for sym in syms:
            if sym.kind == "proposal_section":
                continue
            blob = f"{sym.name} {sym.preview}".lower()
            if not any(q.lower() in blob for q in queries):
                continue
            if sym.id in seen_ids:
                continue
            seen_ids.add(sym.id)
            lines.append(
                f"  • {sym.id} — {sym.name} (lines {sym.start_line}-{sym.end_line})"
            )
            if len(seen_ids) >= MAX_EDIT_HINTS:
                break
        if len(seen_ids) >= MAX_EDIT_HINTS:
            break
    if len(seen_ids) == 0:
        return ""
    return "\n".join(lines)


def merge_duplicate_plan_labels(steps: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop near-duplicate exec labels from over-eager planners."""
    out: list[dict[str, str]] = []
    seen_norm: set[str] = set()
    for step in steps:
        label = str(step.get("label") or "").strip()
        norm = re.sub(r"\s+", " ", label.lower())[:80]
        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        out.append(step)
    return out
