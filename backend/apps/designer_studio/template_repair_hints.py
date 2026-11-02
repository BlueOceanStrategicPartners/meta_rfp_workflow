"""Map validation issue text to scoped pool hints for tool-loop repair."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .agent_rules import hybrid_query_document_score

if TYPE_CHECKING:
    from .template_symbol_index import TemplateSymbol
    from .template_workspace import TemplateWorkspace


def repair_search_hints(issues: list[str]) -> list[dict[str, str]]:
    """Legacy keyword → file/query pairs (used when workspace is unavailable)."""
    hints: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(file: str, query: str) -> None:
        key = (file, query)
        if key in seen:
            return
        seen.add(key)
        hints.append({"file": file, "query": query})

    for issue in issues:
        lower = issue.lower()
        if "cta" in lower or "accept" in lower or "proposal-cta" in lower:
            add("css", "proposal-cta")
            add("css", "display:none")
            add("html", "cta_accept_button")
        if "placeholder" in lower or "{{" in issue:
            add("html", "verified_room_blocks")
            add("html", "room block")
            for token in re.findall(r"\{\{[^}]+\}\}", issue):
                add("html", token)
        if "hardcoded dollar" in lower or "verified_room_blocks" in lower:
            add("html", "verified_room_blocks")
            add("html", "room")
        if "js" in lower or "script" in lower or "onclick" in lower:
            add("js", "onclick")
            add("html", "onclick")
        if "map" in lower or "venue-map" in lower:
            add("html", "venue-map")
            add("html", "selected_map_svg")
        if "responsive" in lower or "breakpoint" in lower or "mobile" in lower:
            add("css", "@media")
        if "date" in lower or "iso" in lower or "mm/dd" in lower:
            add("html", "event_dates")
            add("html", "2026-")
        if "unbalanced" in lower or "<section" in lower or "css" in lower or "style" in lower:
            add("html", "proposal_section", "style")
            add("html", "html_element", "style")

    if not hints:
        add("html", "{{")
    return hints[:8]


def _issue_pool_queries(issue: str) -> list[tuple[str, str, str]]:
    """Return (file, kind, query) tuples for one issue."""
    out: list[tuple[str, str, str]] = []
    lower = issue.lower()

    def push(file: str, kind: str, query: str) -> None:
        out.append((file, kind, query))

    if "css" in lower or "display:none" in lower or "proposal-cta" in lower or "@media" in lower:
        push("css", "css_rule", "proposal-cta" if "cta" in lower else issue[:80])
    if "script" in lower or "js" in lower or "onclick" in lower:
        push("js", "js_symbol", "onclick")
        push("html", "proposal_section", "script")
    if "unbalanced" in lower:
        for tag in re.findall(r"<\s*(\w+)", issue):
            push("html", "proposal_section", tag)
    for token in re.findall(r"\{\{[^}]+\}\}", issue):
        push("html", "proposal_section", token)
    if "map" in lower or "venue" in lower:
        push("html", "proposal_section", "venue map")
    if not out:
        snippet = re.sub(r"\s+", " ", issue).strip()[:100]
        push("html", "proposal_section", snippet or "proposal")
    return out


def _rank_symbol(query: str, sym: "TemplateSymbol") -> float:
    doc = f"{sym.name} {sym.preview}"
    return hybrid_query_document_score(query.lower(), doc)


def repair_pool_hints(
    workspace: "TemplateWorkspace",
    issues: list[str],
    *,
    max_hints: int = 8,
) -> list[dict[str, Any]]:
    """Resolve issues to concrete symbol ids + line ranges for replace_lines."""
    from .template_symbol_index import index_template_file

    hints: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for issue in issues:
        for file, kind, query in _issue_pool_queries(issue):
            try:
                syms = index_template_file(workspace, file)  # type: ignore[arg-type]
            except ValueError:
                continue
            if kind != "all":
                syms = [s for s in syms if s.kind == kind]
            if not syms:
                continue
            scored = sorted(
                (( _rank_symbol(query, s), s) for s in syms),
                key=lambda x: x[0],
                reverse=True,
            )
            sym = scored[0][1]
            if sym.id in seen_ids:
                continue
            seen_ids.add(sym.id)
            hints.append(
                {
                    "file": file,
                    "kind": sym.kind,
                    "query": query,
                    "symbol_id": sym.id,
                    "name": sym.name,
                    "start_line": sym.start_line,
                    "end_line": sym.end_line,
                    "issue_snippet": issue[:160],
                }
            )
            if len(hints) >= max_hints:
                return hints
    return hints


def format_repair_brief(
    *,
    original_message: str,
    issues: list[str],
    workspace: "TemplateWorkspace | None" = None,
) -> str:
    lines = [
        "VALIDATION REPAIR PASS — fix ONLY the listed issues using tools.",
        "Do not redesign unrelated sections. Preserve every {{placeholder}} exactly once.",
        "Room-block / table binding rules: backend/apps/designer_studio/guidance/placeholder_binding.md",
        "Do not revert the user's layout request (alignment, centering, header button sizing) "
        "unless an issue explicitly requires it.",
        "",
        "Issues to fix:",
    ]
    lines.extend(f"- {i}" for i in issues[:12])
    pool = repair_pool_hints(workspace, issues) if workspace else []
    if pool:
        lines.append("")
        lines.append("Pool edit steps (start here — one section at a time):")
        for h in pool:
            lines.append(
                f"- list_template_symbols(file={h['file']!r}, kind={h['kind']!r}, query={h['query']!r})"
            )
            lines.append(
                f"  → read_template_symbol(symbol_id={h['symbol_id']!r}) "
                f"({h['name']}, L{h['start_line']}-{h['end_line']})"
            )
            lines.append(
                f"  → replace_lines(file={h['file']!r}, start_line={h['start_line']}, "
                f"end_line={h['end_line']}, new_content=...)"
            )
    else:
        legacy = repair_search_hints(issues)
        if legacy:
            lines.append("")
            lines.append("Suggested lookups (then use list_template_symbols + replace_lines):")
            for h in legacy:
                lines.append(f"- file={h['file']} query={h['query']!r}")
    if original_message.strip():
        lines.append("")
        lines.append(f"Original user request (context):\n{original_message.strip()[:1500]}")
    return "\n".join(lines)
