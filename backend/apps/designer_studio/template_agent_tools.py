"""Designer template editing tools (server-executed, agent-requested via JSON tool loop)."""
from __future__ import annotations

from typing import Any

from .designer_user_labels import USER_TOOL_LABELS, user_tool_label
from .template_workspace import TemplateFile, TemplateWorkspace, normalize_template_file_arg
from .template_symbol_index import (
    execute_list_template_symbols,
    execute_read_template_symbol,
    execute_search_template,
)

from apps.venue_map_studio.map_knowledge_tools import (
    MAP_KNOWLEDGE_TOOL_NAMES,
    execute_map_knowledge_tool,
)

TOOL_NAMES = frozenset(
    {
        "get_template_overview",
        "list_template_symbols",
        "read_template_symbol",
        "read_template_lines",
        "search_template",
        "replace_exact",
        "replace_lines",
        "append_template",
        "validate_template",
        "lint_template",
        "get_map_knowledge",
        "get_map_reference_code",
    }
)


def _normalize_file(raw: Any) -> TemplateFile:
    return normalize_template_file_arg(raw)


TOOL_HUMAN_LABELS = dict(USER_TOOL_LABELS)


def human_tool_label(tool_name: str) -> str:
    return user_tool_label(tool_name)


def tool_catalog_for_prompt() -> str:
    return (
        "get_template_overview() — line counts and placeholders (SKIP if snapshot + section pool present).\n"
        "New templates use ONE html file (Tailwind CDN + inline <script>). "
        "Edit file=html only; leave css/js empty unless migrating legacy templates.\n"
        "Tool `file` accepts html | css | js (legacy split only for old templates).\n"
        "list_template_symbols(file, kind=all|proposal_section|css_rule|html_element|js_symbol, query?, max_items=24) — "
        "proposal_section = full blocks; optional query uses hybrid BM25 + semantic ranking.\n"
        "read_template_symbol(symbol_id) — full section/symbol body (up to ~24k chars for proposal_section).\n"
        "read_template_lines(file, start_line, end_line) — numbered slice, 1-based inclusive.\n"
        "search_template(file, query, kind=all|proposal_section|css_rule|html_element|js_symbol, "
        "mode=hybrid|line, regex=false, max_hits=12) — "
        "DEFAULT hybrid: ranks HTML sections, Tailwind class hooks, placeholders, CSS rules, "
        "and inline script/style blocks (BM25 + semantic embeddings, same as list_template_symbols). "
        "Returns symbol_id + line span → read_template_symbol. "
        "Use mode=line or regex=true only for exact syntax grep (href=, rare regex).\n"
        "replace_exact(file, old_string, new_string, max_replacements=1) — substring replace.\n"
        "replace_lines(file, start_line, end_line, new_content) — replace line range.\n"
        "append_template(file, content) — append to file end.\n"
        "validate_template(scope=systematic|quick, layout_review=false) — Run anytime to audit Tailwind single-file html_markup. "
        "Checks: Tailwind CDN in <head>, CSS inside <style> (not pasted as plain text in body), "
        "inline <style> syntax (unbalanced braces, stray </style>, bad @apply), "
        "placeholders, JS safety, compile preview, tag balance. Legacy css/js columns should stay empty. "
        "layout_review=true adds Muse layout review. "
        "When valid=false, pool_repair_hints point at html line ranges for replace_lines.\n"
        "lint_template() — fast line-attributed lint (unclosed <script>, JS visible in body, tags, placeholders). "
        "Runs automatically after every edit; call explicitly to re-check.\n"
        "get_map_knowledge(topic=overview|checklist|do_dont|contract|locations_schema|all) — "
        "interactive venue map rules, MUST/AVOID, checklist (Map Knowledge).\n"
        "get_map_reference_code(part=html|css|js|markers|popup_anchor|structure|full, floorplan_url?) — "
        "canonical demo code from venue_map_studio/map_knowledge/interactive-venue-map-reference.html.\n"
        "When building or fixing the venue map section in proposal html, call get_map_knowledge then "
        "get_map_reference_code before editing map-related markup.\n"
        "Finish with {\"kind\":\"finish\",\"assistant_message\":\"...\",\"clarification_options\":[]}."
    )


def execute_template_tool(
    workspace: TemplateWorkspace,
    tool_name: str,
    arguments: dict[str, Any] | None,
    *,
    user_brief: str = "",
) -> dict[str, Any]:
    args = arguments or {}
    name = (tool_name or "").strip()
    if name in MAP_KNOWLEDGE_TOOL_NAMES:
        return execute_map_knowledge_tool(name, args)
    if name not in TOOL_NAMES:
        return {"ok": False, "error": f"Unknown tool '{tool_name}'. Allowed: {sorted(TOOL_NAMES)}"}

    try:
        if name == "get_template_overview":
            ph = workspace.placeholder_report()
            return {
                "ok": True,
                "html_lines": workspace.line_count("html"),
                "css_lines": workspace.line_count("css"),
                "js_lines": workspace.line_count("js"),
                "placeholders_present": ph["present"],
                "placeholders_missing": ph["missing"],
            }

        if name == "list_template_symbols":
            return execute_list_template_symbols(workspace, args)

        if name == "read_template_symbol":
            return execute_read_template_symbol(workspace, args)

        if name == "read_template_lines":
            file = _normalize_file(args.get("file"))
            start = int(args.get("start_line") or 1)
            end = int(args.get("end_line") or start)
            body = workspace.read_lines(file, start, end)
            return {"ok": True, "file": file, "start_line": start, "end_line": end, "content": body}

        if name == "search_template":
            return execute_search_template(workspace, args)
        if name == "replace_exact":
            file = _normalize_file(args.get("file"))
            old = str(args.get("old_string") or "")
            new = str(args.get("new_string") or "")
            if not old:
                return {"ok": False, "error": "old_string is required"}
            max_rep = min(50, max(1, int(args.get("max_replacements") or 1)))
            content = workspace.get_file(file)
            count = content.count(old)
            if count == 0:
                return {"ok": False, "error": "old_string not found", "file": file}
            if count > max_rep and max_rep == 1:
                return {
                    "ok": False,
                    "error": f"old_string matches {count} times; narrow search or raise max_replacements",
                    "file": file,
                }
            replaced = content.replace(old, new, max_rep)
            workspace.set_file(file, replaced)
            return {"ok": True, "file": file, "replacements": min(count, max_rep)}

        if name == "replace_lines":
            file = _normalize_file(args.get("file"))
            start = int(args.get("start_line"))
            end = int(args.get("end_line"))
            new_content = str(args.get("new_content") or "")
            workspace.replace_lines(file, start, end, new_content)
            return {"ok": True, "file": file, "start_line": start, "end_line": end}

        if name == "append_template":
            file = _normalize_file(args.get("file"))
            content = str(args.get("content") or "")
            if not content.strip():
                return {"ok": False, "error": "content is required"}
            workspace.append(file, content)
            return {"ok": True, "file": file, "appended_chars": len(content)}

        if name == "lint_template":
            from .template_lint import lint_template_workspace

            return lint_template_workspace(workspace)

        if name == "validate_template":
            from .designer_validation import (
                validate_template_deterministic_gate,
                validate_template_like_button,
            )
            from .finalize_validation import run_systematic_finalize_validation
            from .template_repair_hints import repair_pool_hints

            brief = str((args or {}).get("user_brief") or user_brief or "")
            scope = str(args.get("scope") or "systematic").strip().lower()
            layout_review = bool(args.get("layout_review"))

            if scope == "quick":
                review = validate_template_deterministic_gate(
                    html=workspace.html_markup,
                    css=workspace.css_stylesheet,
                    js=workspace.js_script,
                    message=brief,
                )
                review = {
                    **review,
                    "compile_issues": [],
                    "structure_issues": [],
                    "style_issues": [],
                }
            elif layout_review:
                review = validate_template_like_button(
                    html=workspace.html_markup,
                    css=workspace.css_stylesheet,
                    js=workspace.js_script,
                    message=brief,
                )
                review = {
                    **review,
                    "compile_issues": [],
                    "structure_issues": [],
                    "style_issues": [],
                }
            else:
                review = run_systematic_finalize_validation(
                    workspace=workspace,
                    message=brief,
                )

            issues = list(review.get("issues") or [])
            valid = bool(review.get("valid"))
            pool_hints = repair_pool_hints(workspace, issues) if not valid else []
            return {
                "ok": True,
                "valid": valid,
                "issues": issues,
                "summary": str(review.get("summary") or ""),
                "deterministic_issues": list(review.get("deterministic_issues") or []),
                "compile_issues": list(review.get("compile_issues") or []),
                "style_issues": list(review.get("style_issues") or []),
                "structure_issues": list(review.get("structure_issues") or []),
                "muse_issues": list(review.get("muse_issues") or []),
                "pool_repair_hints": pool_hints,
                "agent_workflow": (
                    "If valid=false: for each issue use pool_repair_hints — "
                    "list_template_symbols(file, kind, query) → read_template_symbol(symbol_id) → "
                    "replace_lines(file, start_line, end_line, new_content). "
                    "Re-run validate_template after fixes."
                ),
                "scope": scope if scope in ("quick", "systematic") else "systematic",
                "layout_review": layout_review,
            }

    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except (TypeError, KeyError) as exc:
        return {"ok": False, "error": f"Invalid arguments: {exc}"}

    return {"ok": False, "error": "Unhandled tool"}
