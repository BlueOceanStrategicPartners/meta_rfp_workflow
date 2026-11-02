"""Systematic HTML/template validation at finalize (tool-loop finish + chat wrap-up)."""
from __future__ import annotations

import re
from typing import Any

from apps.core.exceptions import TemplateValidationException

from .designer_validation import validate_template_deterministic_gate
from .services import compile_template
from .single_file_template import template_storage_mode
from .tailwind_embedded_validation import collect_tailwind_and_embedded_style_issues
from .template_repair_hints import format_repair_brief
from .template_workspace import TemplateWorkspace

_BALANCE_TAGS = ("html", "head", "body", "main", "section", "header", "footer", "script", "style")


def collect_compile_issues(*, html: str, css: str, js: str) -> list[str]:
    try:
        compile_template(html, css, js_script=js)
    except TemplateValidationException as exc:
        return [str(exc)]
    except Exception as exc:  # pragma: no cover - defensive
        return [f"Compile/preview failed: {exc}"]
    return []


def collect_html_tag_balance_issues(html: str) -> list[str]:
    """Fast structural sanity check for single-file / full-document HTML."""
    text = html or ""
    if not text.strip():
        return ["HTML body is empty."]
    issues: list[str] = []
    for tag in _BALANCE_TAGS:
        opens = len(re.findall(rf"<\s*{tag}(?:\s[^>]*)?>", text, flags=re.I))
        self_closing = len(re.findall(rf"<\s*{tag}(?:\s[^>]*)?/\s*>", text, flags=re.I))
        opens = max(0, opens - self_closing)
        closes = len(re.findall(rf"<\s*/\s*{tag}\s*>", text, flags=re.I))
        if opens == 0 and closes == 0:
            continue
        if opens != closes:
            issues.append(
                f"Unbalanced <{tag}> tags: {opens} opening vs {closes} closing "
                "(fix markup before finalize)."
            )
    return issues


def run_systematic_finalize_validation(
    *,
    workspace: TemplateWorkspace,
    message: str = "",
    history: list[dict[str, str]] | None = None,
    include_structure: bool = True,
) -> dict[str, Any]:
    """Deterministic gate + compile preview + optional tag-balance checks."""
    html = workspace.html_markup or ""
    css = workspace.css_stylesheet or ""
    js = workspace.js_script or ""

    det = validate_template_deterministic_gate(
        html=html,
        css=css,
        js=js,
        message=message,
        history=history,
    )
    compile_issues = collect_compile_issues(html=html, css=css, js=js)
    style_issues = collect_tailwind_and_embedded_style_issues(html, css, js)
    structure_issues: list[str] = []
    if include_structure:
        mode = template_storage_mode(html, css, js)
        if mode == "single" or "<!doctype" in html.lower():
            structure_issues = collect_html_tag_balance_issues(html)

    seen: set[str] = set()
    all_issues: list[str] = []
    for bucket in (
        list(det.get("issues") or []),
        compile_issues,
        style_issues,
        structure_issues,
    ):
        for item in bucket:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                all_issues.append(text)

    valid = not all_issues
    summary = "Finalize validation passed." if valid else "; ".join(all_issues[:5])
    return {
        "valid": valid,
        "issues": all_issues,
        "summary": summary,
        "deterministic_issues": list(det.get("issues") or []),
        "compile_issues": compile_issues,
        "style_issues": style_issues,
        "structure_issues": structure_issues,
    }


def format_finalize_reject_message(
    *,
    workspace: TemplateWorkspace,
    review: dict[str, Any],
    original_message: str,
) -> str:
    issues = list(review.get("issues") or [])
    lines = [
        "FINALIZE VALIDATION FAILED — your finish attempt was rejected.",
        "Run FIX VALIDATION workflow: fix ONLY the listed issues using pool tools "
        "(list_template_symbols → read_template_symbol → replace_lines).",
        "Do not call finish again until validation passes.",
        "",
        "Systematic validation report:",
    ]
    for item in issues[:16]:
        lines.append(f"- {item}")
    brief = format_repair_brief(
        original_message=original_message,
        issues=issues,
        workspace=workspace,
    )
    lines.append("")
    lines.append(brief)
    return "\n".join(lines)
