"""Designer template editing tools (server-executed, agent-requested via JSON tool loop)."""
from __future__ import annotations

import re
from typing import Any

from .designer_user_labels import USER_TOOL_LABELS, user_tool_label
from .template_workspace import TemplateFile, TemplateWorkspace, normalize_template_file_arg
from .template_symbol_index import execute_list_template_symbols, execute_read_template_symbol

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
    }
)


def _normalize_file(raw: Any) -> TemplateFile:
    return normalize_template_file_arg(raw)


TOOL_HUMAN_LABELS = dict(USER_TOOL_LABELS)


def human_tool_label(tool_name: str) -> str:
    return user_tool_label(tool_name)


def tool_catalog_for_prompt() -> str:
    return (
        "get_template_overview() — line counts and required {{placeholder}} checklist.\n"
        "All tools that take `file` accept ONLY: html | css | js "
        "(same as the three template parts — never html_markup or css_stylesheet as file names).\n"
        "list_template_symbols(file, kind=all|css_rule|html_element|js_symbol, query?, max_items=24) — "
        "AST-style index (selectors, #ids, functions) with line ranges.\n"
        "read_template_symbol(symbol_id) — full symbol body from list_template_symbols (preferred over wide line reads).\n"
        "read_template_lines(file, start_line, end_line) — numbered slice, 1-based inclusive.\n"
        "search_template(file, query, regex=false, max_hits=12) — line hits with snippets.\n"
        "replace_exact(file, old_string, new_string, max_replacements=1) — substring replace.\n"
        "replace_lines(file, start_line, end_line, new_content) — replace line range.\n"
        "append_template(file, content) — append to file end.\n"
        "validate_template() — same checks as Check template (deterministic + layout review).\n"
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
            file = _normalize_file(args.get("file"))
            query = str(args.get("query") or "")
            if not query:
                return {"ok": False, "error": "query is required"}
            use_regex = bool(args.get("regex"))
            max_hits = min(40, max(1, int(args.get("max_hits") or 12)))
            text = workspace.get_file(file)
            hits: list[dict[str, Any]] = []
            for i, line in enumerate(text.splitlines(), start=1):
                matched = False
                if use_regex:
                    try:
                        matched = re.search(query, line) is not None
                    except re.error as exc:
                        return {"ok": False, "error": f"Invalid regex: {exc}"}
                else:
                    matched = query in line
                if matched:
                    hits.append({"line": i, "text": line[:240]})
                if len(hits) >= max_hits:
                    break
            return {"ok": True, "file": file, "query": query, "hits": hits, "total_shown": len(hits)}

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

        if name == "validate_template":
            from .designer_validation import validate_template_like_button

            brief = str((args or {}).get("user_brief") or user_brief or "")
            review = validate_template_like_button(
                html=workspace.html_markup,
                css=workspace.css_stylesheet,
                js=workspace.js_script,
                message=brief,
            )
            issues = list(review.get("issues") or [])
            return {
                "ok": True,
                "valid": bool(review.get("valid")),
                "issues": issues,
                "summary": str(review.get("summary") or ""),
                "deterministic_issues": review.get("deterministic_issues") or [],
                "muse_issues": review.get("muse_issues") or [],
            }

    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except (TypeError, KeyError) as exc:
        return {"ok": False, "error": f"Invalid arguments: {exc}"}

    return {"ok": False, "error": "Unhandled tool"}
